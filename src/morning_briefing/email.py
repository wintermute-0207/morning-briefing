"""Email generation and sending."""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests


EMAIL_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Briefing</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #1a1a1a;
            line-height: 1.6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
        }}
        .header {{
            background: linear-gradient(135deg, #1a237e 0%, #3949ab 100%);
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 28px;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        .header .date {{
            color: rgba(255,255,255,0.8);
            font-size: 14px;
            margin-top: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .content {{ padding: 40px 30px; }}
        .story {{
            margin-bottom: 40px;
            padding-bottom: 40px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .story:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
        .category {{
            display: inline-block;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #3949ab;
            margin-bottom: 12px;
            padding: 4px 12px;
            background: #e8eaf6;
            border-radius: 4px;
        }}
        .story h2 {{
            margin: 0 0 18px 0;
            font-size: 20px;
            font-weight: 600;
            line-height: 1.35;
        }}
        .story h2 a {{ color: #1a1a1a; text-decoration: none; }}
        .story h2 a:hover {{ color: #3949ab; }}
        .executive-summary {{
            font-size: 15px;
            line-height: 1.7;
            color: #333;
            margin: 18px 0;
            padding: 0;
        }}
        .significance {{
            margin: 20px 0;
            padding: 14px 18px;
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            font-size: 14px;
            line-height: 1.6;
            color: #1565c0;
        }}
        .significance strong {{ 
            color: #0d47a1; 
            display: block;
            margin-bottom: 6px;
        }}
        .hn-synthesis {{
            margin: 20px 0 0 0;
            padding: 16px 18px;
            background: #fff8e1;
            border-left: 4px solid #ffc107;
        }}
        .hn-synthesis-header {{
            font-size: 12px;
            font-weight: 600;
            color: #e65100;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        .hn-synthesis-text {{
            font-size: 14px;
            line-height: 1.6;
            color: #555;
        }}
        .source {{
            font-size: 12px;
            color: #888;
            margin-top: 18px;
        }}
        .source a {{ 
            color: #3949ab; 
            text-decoration: none;
            border-bottom: 1px solid #c5cae9;
        }}
        .footer {{
            padding: 30px;
            text-align: center;
            background-color: #fafafa;
            border-top: 1px solid #e0e0e0;
        }}
        .footer p {{ margin: 0; font-size: 13px; color: #888; }}
        .footer .signature {{ color: #3949ab; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Morning Briefing</h1>
            <div class="date">{date}</div>
        </div>
        <div class="content">
            {stories}
        </div>
        <div class="footer">
            <p>Curated for you by <span class="signature">Wintermute ❄️</span></p>
            <p style="margin-top: 8px; font-size: 12px;">{item_count} stories</p>
        </div>
    </div>
</body>
</html>
'''


def format_story(title: str, url: str, executive_summary: str,
                 significance: str, source: str, category: str = "",
                 hn_synthesis: Optional[str] = None) -> str:
    """Format a single story as HTML with executive summary."""
    cat_display = f"{source.upper()} · {category.upper()}" if category else source.upper()
    
    html = f'''
<div class="story">
    <span class="category">{cat_display}</span>
    <h2><a href="{url}">{title}</a></h2>
    
    <div class="executive-summary">
        {executive_summary}
    </div>
    
    <div class="significance">
        <strong>Why this matters:</strong>
        {significance}
    </div>
'''
    
    if hn_synthesis:
        html += f'''
    <div class="hn-synthesis">
        <div class="hn-synthesis-header">💡 HN Discussion Synthesis</div>
        <div class="hn-synthesis-text">{hn_synthesis}</div>
    </div>
'''
    
    html += f'<p class="source">Read more at <a href="{url}">{source}</a></p>'
    html += '</div>'
    return html


def generate_email(stories_html: list[str], date: Optional[str] = None) -> str:
    """Generate complete HTML email."""
    date = date or datetime.now().strftime('%B %d, %Y')
    stories = '\n'.join(stories_html)
    
    return EMAIL_TEMPLATE.format(
        date=date,
        stories=stories,
        item_count=len(stories_html)
    )


def save_email(html: str, output_dir: Path, date: Optional[str] = None) -> Path:
    """Save email HTML to file."""
    date = date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    path = output_dir / f"{date}.html"
    path.write_text(html, encoding='utf-8')
    return path


def send_email_sendgrid(html_path: Path, to: str, subject: str,
                        sendgrid_config: dict) -> bool:
    """Send email via SendGrid API."""
    api_key = sendgrid_config.get('api_key')
    from_email = sendgrid_config.get('from')
    from_name = sendgrid_config.get('from_name', 'Morning Briefing')
    
    html_content = html_path.read_text()
    
    # Create plain text version
    import re
    text_content = re.sub(r'<[^>]+>', ' ', html_content)
    text_content = re.sub(r'\s+', ' ', text_content).strip()[:500]
    
    payload = {
        "personalizations": [
            {
                "to": [{"email": to}]
            }
        ],
        "from": {
            "email": from_email,
            "name": from_name
        },
        "subject": subject,
        "content": [
            {
                "type": "text/plain",
                "value": text_content + "\n\nView the full HTML version for better formatting."
            },
            {
                "type": "text/html",
                "value": html_content
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 202:
            return True
        else:
            print(f"SendGrid error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"SendGrid send failed: {e}")
        return False


def send_email_smtp(html_path: Path, to: str, subject: str,
                    smtp_config: dict) -> bool:
    """Send email via SMTP using curl."""
    
    boundary = f"boundary_{datetime.now().timestamp()}"
    
    email_content = f'''From: {smtp_config['from']}
To: {to}
Subject: {subject}
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="{boundary}"

--{boundary}
Content-Type: text/plain; charset="UTF-8"

Morning Briefing - see HTML version in your email client.

--{boundary}
Content-Type: text/html; charset="UTF-8"

{html_path.read_text()}

--{boundary}--
'''
    
    temp_path = Path('/tmp') / f"email_{datetime.now().timestamp()}.txt"
    temp_path.write_text(email_content)
    
    try:
        result = subprocess.run([
            'curl', '-s', '--url', f'smtps://{smtp_config["host"]}:{smtp_config["port"]}',
            '--ssl-reqd',
            '--mail-from', smtp_config['from'],
            '--mail-rcpt', to,
            '--upload-file', str(temp_path),
            '--user', f"{smtp_config['username']}:{smtp_config['password']}"
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    finally:
        temp_path.unlink(missing_ok=True)


def send_email(html_path: Path, to: str, subject: str,
               email_config: dict) -> bool:
    """Send email using configured provider (sendgrid or smtp)."""
    provider = email_config.get('provider', 'smtp').lower()
    
    if provider == 'sendgrid':
        return send_email_sendgrid(html_path, to, subject, email_config)
    else:
        return send_email_smtp(html_path, to, subject, email_config)
