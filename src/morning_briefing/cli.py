"""Command-line interface for morning-briefing."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .database import Database
from .email import send_email
from .pipeline import run_pipeline, items_from_result

DEFAULT_CONFIG_PATH = Path.home() / '.config/morning-briefing/config.json'
DEFAULT_OUTPUT_DIR = Path.home() / '.local/share/morning-briefing/emails'


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from file."""
    if not path.exists():
        print(f"Config not found at {path}")
        print("Create it with your SMTP settings.")
        sys.exit(1)

    return json.loads(path.read_text())


def cmd_generate(args):
    """Generate and optionally send briefing using the 3-stage pipeline."""
    config = load_config()
    db = Database()

    result = run_pipeline(config, db, DEFAULT_OUTPUT_DIR)

    if not result.html_path:
        if result.skipped_reason:
            print(f"\nNo email generated: {result.skipped_reason}")
        return

    # Send if requested
    if args.send:
        email_cfg = config['email']
        subject = f"Morning Briefing - {datetime.now().strftime('%B %d, %Y')}"

        print(f"Sending to {email_cfg['to']}...")
        if send_email(result.html_path, email_cfg['to'], subject, email_cfg):
            print("Sent!")

            items = items_from_result(result)
            email_id = db.record_email(
                subject=subject,
                recipient=email_cfg['to'],
                html_path=result.html_path,
                items=items,
            )
            print(f"Recorded as email #{email_id}")
        else:
            print("Failed to send")


def cmd_list(args):
    """List recent emails."""
    db = Database()
    emails = db.get_recent_emails(args.limit)
    
    for email in emails:
        print(f"\n[{email['id']}] {email['sent_at']}")
        print(f"    Subject: {email['subject']}")
        print(f"    Sources: {', '.join(email['sources'])}")
        for item in email['items']:
            rating = f"★{item['avg_rating']:.1f}" if item['avg_rating'] else "☆"
            print(f"    - [{rating}] {item['title'][:60]}... (ID: {item['id']})")


def cmd_feedback(args):
    """Add feedback on an item."""
    db = Database()
    
    item_id = None
    if args.item.isdigit():
        item_id = int(args.item)
    else:
        item_id = db.find_item_by_url(args.item)
    
    if not item_id:
        print(f"Item not found: {args.item}")
        sys.exit(1)
    
    if db.add_feedback(item_id, args.rating, args.comment or ""):
        print(f"Feedback recorded: {args.rating}/5 for item {item_id}")
    else:
        print("Failed to record feedback")


def cmd_stats(args):
    """Show feedback statistics."""
    db = Database()
    stats = db.get_feedback_stats()
    
    print("\nFeedback by Source:")
    for source, data in stats.items():
        print(f"  {source:15} {data['avg_rating']:.1f}/5 ({data['count']} ratings)")


def cmd_top(args):
    """Show top-rated items."""
    db = Database()
    items = db.get_top_items(min_rating=args.min_rating, limit=args.limit)
    
    print(f"\nTop-rated items (≥{args.min_rating}/5):")
    for item in items:
        print(f"\n  [{item['rating']:.1f}/5] {item['title'][:70]}")
        print(f"      Source: {item['source']} | {item['category']}")
        if item.get('comments'):
            print(f"      Note: {item['comments'][:100]}")


def cmd_sent(args):
    """Check if URL was already sent."""
    db = Database()
    if db.has_been_sent(args.url):
        print(f"✓ Already sent: {args.url}")
    else:
        print(f"✗ Not yet sent: {args.url}")


def main():
    parser = argparse.ArgumentParser(
        prog='mbrief',
        description='Personalized morning news briefing'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    gen_parser = subparsers.add_parser('generate', help='Generate briefing')
    gen_parser.add_argument('--send', action='store_true', help='Send via email')
    gen_parser.set_defaults(func=cmd_generate)
    
    list_parser = subparsers.add_parser('list', help='List recent emails')
    list_parser.add_argument('--limit', '-n', type=int, default=10)
    list_parser.set_defaults(func=cmd_list)
    
    fb_parser = subparsers.add_parser('feedback', help='Rate an item')
    fb_parser.add_argument('item', help='Item ID or URL')
    fb_parser.add_argument('--rating', '-r', type=int, required=True, help='1-5 stars')
    fb_parser.add_argument('--comment', '-c', help='Optional comment')
    fb_parser.set_defaults(func=cmd_feedback)
    
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    top_parser = subparsers.add_parser('top', help='Show top-rated items')
    top_parser.add_argument('--min-rating', type=float, default=4.0)
    top_parser.add_argument('--limit', '-n', type=int, default=10)
    top_parser.set_defaults(func=cmd_top)
    
    sent_parser = subparsers.add_parser('sent', help='Check if URL was sent')
    sent_parser.add_argument('url', help='URL to check')
    sent_parser.set_defaults(func=cmd_sent)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
