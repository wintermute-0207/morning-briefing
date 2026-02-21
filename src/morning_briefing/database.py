"""Database models and tracking for sent items and feedback."""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path.home() / ".local/share/morning-briefing/briefing.db"


@dataclass
class Item:
    """A single content item (story, paper, article)."""
    
    source: str  # 'hn', 'arxiv', 'mailing_list', 'web_search'
    title: str
    url: str
    summary: str
    category: str = ""
    source_id: str = ""
    
    # HN specific
    hn_points: int = 0
    hn_comments: int = 0
    
    # arXiv specific
    arxiv_authors: list = None
    traction_score: float = 0.0
    
    # Mailing list specific
    mailing_list_sender: str = ""
    
    def __post_init__(self):
        if self.arxiv_authors is None:
            self.arxiv_authors = []


class Database:
    """SQLite database for tracking emails and feedback."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    subject TEXT,
                    recipient TEXT,
                    html_path TEXT,
                    summary TEXT,
                    sources_json TEXT
                );
                
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER,
                    source TEXT,
                    source_id TEXT,
                    title TEXT,
                    url TEXT UNIQUE,
                    category TEXT,
                    summary TEXT,
                    traction_score REAL,
                    hn_points INTEGER,
                    hn_comments INTEGER,
                    arxiv_authors TEXT,
                    mailing_list_sender TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails(id)
                );
                
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    email_id INTEGER,
                    rating INTEGER,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES items(id),
                    FOREIGN KEY (email_id) REFERENCES emails(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_items_url ON items(url);
                CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
                CREATE INDEX IF NOT EXISTS idx_feedback_item ON feedback(item_id);
            ''')
    
    def has_been_sent(self, url: str) -> bool:
        """Check if a URL has been sent before."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT 1 FROM items WHERE url = ?', (url,)
            )
            return cursor.fetchone() is not None
    
    def record_email(self, subject: str, recipient: str, 
                     html_path: Path, items: list[Item]) -> int:
        """Record a sent email and its items. Returns email_id."""
        with sqlite3.connect(self.db_path) as conn:
            # Insert email
            cursor = conn.execute('''
                INSERT INTO emails (subject, recipient, html_path, summary, sources_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                subject, recipient, str(html_path),
                f"{len(items)} items",
                json.dumps(list(set(i.source for i in items)))
            ))
            email_id = cursor.lastrowid
            
            # Insert items
            for item in items:
                conn.execute('''
                    INSERT OR IGNORE INTO items 
                    (email_id, source, source_id, title, url, category, summary,
                     traction_score, hn_points, hn_comments, arxiv_authors, mailing_list_sender)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email_id, item.source, item.source_id, item.title, item.url,
                    item.category, item.summary, item.traction_score,
                    item.hn_points, item.hn_comments,
                    json.dumps(item.arxiv_authors), item.mailing_list_sender
                ))
            
            return email_id
    
    def add_feedback(self, item_id: int, rating: int, comment: str = "") -> bool:
        """Add feedback on an item."""
        with sqlite3.connect(self.db_path) as conn:
            # Get email_id for this item
            cursor = conn.execute(
                'SELECT email_id FROM items WHERE id = ?', (item_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            
            conn.execute('''
                INSERT INTO feedback (item_id, email_id, rating, comment)
                VALUES (?, ?, ?, ?)
            ''', (item_id, row[0], rating, comment))
            return True
    
    def find_item_by_url(self, url: str) -> Optional[int]:
        """Find item ID by URL."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT id FROM items WHERE url = ? ORDER BY id DESC LIMIT 1',
                (url,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_recent_emails(self, limit: int = 10) -> list[dict]:
        """Get recent emails with their items."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            emails = conn.execute('''
                SELECT id, sent_at, subject, sources_json
                FROM emails ORDER BY sent_at DESC LIMIT ?
            ''', (limit,)).fetchall()
            
            result = []
            for email in emails:
                items = conn.execute('''
                    SELECT i.id, i.source, i.title, i.url, 
                           AVG(f.rating) as avg_rating
                    FROM items i
                    LEFT JOIN feedback f ON i.id = f.item_id
                    WHERE i.email_id = ?
                    GROUP BY i.id
                ''', (email['id'],)).fetchall()
                
                result.append({
                    'id': email['id'],
                    'sent_at': email['sent_at'],
                    'subject': email['subject'],
                    'sources': json.loads(email['sources_json']) if email['sources_json'] else [],
                    'items': [dict(i) for i in items]
                })
            
            return result
    
    def get_feedback_stats(self) -> dict:
        """Get aggregate feedback statistics by source."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('''
                SELECT i.source, AVG(f.rating), COUNT(*)
                FROM feedback f
                JOIN items i ON f.item_id = i.id
                GROUP BY i.source
            ''').fetchall()
            
            return {
                row[0]: {'avg_rating': round(row[1], 2), 'count': row[2]}
                for row in rows
            }
    
    def get_top_items(self, min_rating: float = 4.0, limit: int = 20) -> list[dict]:
        """Get highly rated items."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT i.title, i.source, i.category, i.url, 
                       AVG(f.rating) as rating, 
                       GROUP_CONCAT(f.comment) as comments
                FROM feedback f
                JOIN items i ON f.item_id = i.id
                GROUP BY i.id
                HAVING AVG(f.rating) >= ?
                ORDER BY AVG(f.rating) DESC
                LIMIT ?
            ''', (min_rating, limit)).fetchall()
            
            return [dict(row) for row in rows]
