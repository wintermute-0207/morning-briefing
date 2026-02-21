#!/usr/bin/env python3
"""
Test harness for morning briefing - generate emails for review without sending.
Usage: python3 test_harness.py [--date YYYY-MM-DD] [--count N]
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/home/openclaw/.openclaw/workspace/projects/morning-briefing/src')

from morning_briefing.database import Database, Item
from morning_briefing.sources import HackerNewsSource, ArxivSource
from morning_briefing.email import format_story, generate_email, save_email
from morning_briefing.extractor import extract_and_summarize

TEST_OUTPUT_DIR = Path('/home/openclaw/.openclaw/workspace/projects/morning-briefing/test_emails')


def generate_test_email(date_str: str = None, verbose: bool = True):
    """Generate a test email for a specific date (or today)."""
    
    date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
    
    # Use a temporary in-memory DB for testing (no persistence)
    db_path = Path(f'/tmp/test_db_{date.strftime("%Y%m%d")}.db')
    if db_path.exists():
        db_path.unlink()
    db = Database(db_path)
    
    items_to_send = []
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Generating test briefing for {date.strftime('%B %d, %Y')}")
        print(f"{'='*60}")
    
    # Fetch HN stories
    if verbose:
        print("\nFetching Hacker News...")
    hn = HackerNewsSource()
    stories = hn.fetch_top_stories(limit=50)
    filtered = hn.filter_interesting(stories, min_score=25)
    
    for story in filtered[:5]:
        if verbose:
            print(f"\n  → Processing: {story.title[:60]}...")
        
        extracted = extract_and_summarize(story.url, story.title, story.id)
        
        if verbose:
            print(f"    Executive summary: {extracted.executive_summary[:100]}...")
            print(f"    Significance: {extracted.significance[:80]}...")
            if extracted.hn_synthesis:
                print(f"    HN synthesis: {extracted.hn_synthesis[:100]}...")
            else:
                print(f"    HN synthesis: None")
        
        items_to_send.append({
            'item': Item(
                source='hn',
                source_id=str(story.id),
                title=story.title,
                url=story.url,
                summary=extracted.executive_summary,
                category=story.category,
                hn_points=story.score,
                hn_comments=story.comments
            ),
            'executive_summary': extracted.executive_summary,
            'significance': extracted.significance,
            'hn_synthesis': extracted.hn_synthesis
        })
    
    if verbose:
        print(f"\n  Selected {len(items_to_send)} stories")
    
    # Fetch arXiv
    if verbose:
        print("\nFetching arXiv...")
    arxiv = ArxivSource()
    papers = arxiv.fetch_recent(days=7, max_per_cat=10)
    
    scored_papers = []
    for paper in papers[:15]:
        score = 0
        if paper.hn_mentioned:
            score += 30
        if paper.github_repos:
            score += 20
        if score >= 5:
            scored_papers.append((score, paper))
    
    scored_papers.sort(reverse=True)
    
    for score, paper in scored_papers[:2]:
        if verbose:
            print(f"\n  → Processing arXiv: {paper.title[:60]}...")
        
        exec_summary = paper.summary[:400]
        if len(paper.summary) > 400:
            exec_summary += "..."
        
        significance = f"Recent research in {paper.categories[0] if paper.categories else 'CS'}"
        if paper.github_repos:
            significance += " with available implementation"
        significance += " — potential relevance to technical work."
        
        items_to_send.append({
            'item': Item(
                source='arxiv',
                source_id=paper.id,
                title=paper.title,
                url=paper.url,
                summary=exec_summary,
                category='research',
                traction_score=score,
                arxiv_authors=paper.authors[:3]
            ),
            'executive_summary': exec_summary,
            'significance': significance,
            'hn_synthesis': None
        })
        
        if verbose:
            print(f"    Traction score: {score}")
    
    if not items_to_send:
        print("  No items to include!")
        return None
    
    # Generate HTML
    if verbose:
        print(f"\nGenerating HTML with {len(items_to_send)} items...")
    
    stories_html = []
    for data in items_to_send:
        item = data['item']
        stories_html.append(format_story(
            title=item.title,
            url=item.url,
            executive_summary=data['executive_summary'],
            significance=data['significance'],
            source=item.source,
            category=item.category,
            hn_synthesis=data.get('hn_synthesis')
        ))
    
    html = generate_email(stories_html, date.strftime('%B %d, %Y'))
    
    # Save to test directory
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = save_email(html, TEST_OUTPUT_DIR, date.strftime('%Y-%m-%d'))
    
    if verbose:
        print(f"Saved to: {html_path}")
    
    return html_path


def review_email(html_path: Path):
    """Display email content for review."""
    print(f"\n{'='*60}")
    print(f"REVIEW: {html_path.name}")
    print(f"{'='*60}")
    
    content = html_path.read_text()
    
    # Extract story content for review
    import re
    stories = re.findall(r'<div class="story">(.*?)</div>\s*<p class="source">', content, re.DOTALL)
    
    for i, story in enumerate(stories, 1):
        print(f"\n--- Story {i} ---")
        
        # Extract title
        title_match = re.search(r'<h2><a[^>]*>(.*?)</a></h2>', story)
        if title_match:
            print(f"Title: {title_match.group(1)}")
        
        # Extract executive summary
        summary_match = re.search(r'<div class="executive-summary">(.*?)</div>', story, re.DOTALL)
        if summary_match:
            summary = re.sub(r'<[^>]+>', '', summary_match.group(1))
            summary = re.sub(r'\s+', ' ', summary).strip()
            print(f"\nSummary: {summary[:200]}...")
        
        # Extract significance
        sig_match = re.search(r'<div class="significance">.*?<strong>.*?</strong>(.*?)</div>', story, re.DOTALL)
        if sig_match:
            sig = re.sub(r'<[^>]+>', '', sig_match.group(1))
            sig = re.sub(r'\s+', ' ', sig).strip()
            print(f"\nSignificance: {sig}")
        
        # Extract HN synthesis
        hn_match = re.search(r'<div class="hn-synthesis-text">(.*?)</div>', story, re.DOTALL)
        if hn_match:
            hn = re.sub(r'<[^>]+>', '', hn_match.group(1))
            hn = re.sub(r'\s+', ' ', hn).strip()
            print(f"\nHN Synthesis: {hn[:250]}...")
        else:
            print("\nHN Synthesis: None")
        
        # Quality check
        print("\n--- Quality Check ---")
        issues = []
        
        if summary_match:
            summary_text = re.sub(r'<[^>]+>', '', summary_match.group(1))
            if len(summary_text) < 100:
                issues.append("⚠ Summary too short")
            if '...' in summary_text[-10:]:
                issues.append("⚠ Summary ends abruptly")
        
        if hn_match:
            hn_text = re.sub(r'<[^>]+>', '', hn_match.group(1))
            if '[0]' in hn_text or '[1]' in hn_text:
                issues.append("⚠ HN synthesis has citation artifacts")
            if hn_text.count('.') < 2:
                issues.append("⚠ HN synthesis lacks complete sentences")
            if len(hn_text) > 0 and len(hn_text) < 80:
                issues.append("⚠ HN synthesis suspiciously short")
        
        if not issues:
            print("✓ No obvious issues detected")
        else:
            for issue in issues:
                print(issue)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test morning briefing generation')
    parser.add_argument('--date', help='Generate for specific date (YYYY-MM-DD)')
    parser.add_argument('--count', '-n', type=int, default=1, help='Generate N test emails')
    parser.add_argument('--review', '-r', action='store_true', help='Review generated emails')
    args = parser.parse_args()
    
    if args.date:
        # Generate for specific date
        html_path = generate_test_email(args.date)
        if html_path and args.review:
            review_email(html_path)
    else:
        # Generate for last N days
        for i in range(args.count):
            date = datetime.now() - timedelta(days=i)
            html_path = generate_test_email(date.strftime('%Y-%m-%d'))
            if html_path and args.review:
                review_email(html_path)
                print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
