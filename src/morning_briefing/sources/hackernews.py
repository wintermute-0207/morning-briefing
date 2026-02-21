"""Hacker News source - fetch and filter stories."""

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class HNStory:
    """A Hacker News story."""
    id: int
    title: str
    url: str
    score: int
    comments: int
    top_comments: list[str]
    category: str = "tech"


class HackerNewsSource:
    """Fetch and filter HN stories."""
    
    # Keywords to categorize stories
    CATEGORIES = {
        'tech': ['ai', 'llm', 'claude', 'gpt', 'machine learning', 'database', 
                 'infrastructure', 'cloud', 'kubernetes', 'observability',
                 'mcp', 'server', 'api', 'code', 'programming', 'developer'],
        'economics': ['startup', 'business', 'finance', 'market', 'economy',
                      'valuation', 'revenue', 'profit', 'venture', 'ipo'],
        'science': ['physics', 'biology', 'research', 'study', 'paper',
                    'experiment', 'discovery', 'breakthrough'],
        'f1': ['formula 1', 'f1', 'racing', 'grand prix', 'ferrari', 'red bull',
               'mercedes', 'verstappen', 'hamilton', 'leclerc'],
    }
    
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_top_stories(self, limit: int = 30) -> list[HNStory]:
        """Fetch top stories from HN."""
        # Get top story IDs
        resp = self.session.get(
            'https://hacker-news.firebaseio.com/v0/topstories.json',
            timeout=30
        )
        story_ids = resp.json()[:limit]
        
        stories = []
        for story_id in story_ids:
            story = self._fetch_story(story_id)
            if story:
                stories.append(story)
        
        return stories
    
    def _fetch_story(self, story_id: int) -> Optional[HNStory]:
        """Fetch a single story with its top comments."""
        try:
            resp = self.session.get(
                f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
                timeout=10
            )
            data = resp.json()
            
            if not data or data.get('type') != 'story':
                return None
            
            # Skip self-posts (Ask HN, etc.)
            url = data.get('url', '')
            if not url or url.startswith('item?id='):
                return None
            
            # Get top comments
            comment_ids = data.get('kids', [])[:3]
            top_comments = []
            for cid in comment_ids:
                c = self._fetch_comment(cid)
                if c:
                    top_comments.append(c[:300])  # Truncate long comments
            
            # Categorize
            title_lower = data.get('title', '').lower()
            category = self._categorize(title_lower)
            
            return HNStory(
                id=story_id,
                title=data.get('title', ''),
                url=url,
                score=data.get('score', 0),
                comments=data.get('descendants', 0),
                top_comments=top_comments,
                category=category
            )
        
        except Exception:
            return None
    
    def _fetch_comment(self, comment_id: int) -> Optional[str]:
        """Fetch a single comment text."""
        try:
            resp = self.session.get(
                f'https://hacker-news.firebaseio.com/v0/item/{comment_id}.json',
                timeout=10
            )
            data = resp.json()
            
            if data and data.get('type') == 'comment':
                text = data.get('text', '')
                # Basic HTML tag stripping
                import re
                text = re.sub(r'<[^>]+>', ' ', text)
                return text.strip()
            return None
        except Exception:
            return None
    
    def _categorize(self, title: str) -> str:
        """Categorize a story based on title keywords."""
        scores = {}
        for cat, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in title)
            if score > 0:
                scores[cat] = score
        
        return max(scores, key=scores.get) if scores else 'tech'
    
    def filter_interesting(self, stories: list[HNStory], 
                          min_score: int = 50,
                          min_comments: int = 10) -> list[HNStory]:
        """Filter for interesting stories based on engagement."""
        filtered = [
            s for s in stories
            if s.score >= min_score and s.comments >= min_comments
        ]
        # Sort by score descending
        return sorted(filtered, key=lambda x: x.score, reverse=True)
