"""Content extraction and executive summarization for briefing items."""

import re
from typing import Optional
import requests
from dataclasses import dataclass


@dataclass
class ExtractedContent:
    """Extracted and analyzed content from an article."""
    title: str
    url: str
    executive_summary: str
    significance: str
    hn_synthesis: Optional[str] = None


def extract_article_content(url: str) -> Optional[str]:
    """Extract readable content from a URL."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, 
                                       include_tables=False, deduplicate=True)
            return text[:8000] if text else None
    except ImportError:
        pass
    
    try:
        resp = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        html = resp.text
        
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        
        for pattern in [r'<article[^>]*>(.*?)</article>', r'<main[^>]*>(.*?)</main>']:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                break
        else:
            content = html
        
        text = re.sub(r'<[^>]+>', ' ', content)
        text = re.sub(r'\s+', ' ', text)
        return text[:8000].strip()
    except Exception:
        return None


def synthesize_executive_summary(content: str, title: str) -> str:
    """Create a cohesive narrative summary (2-3 sentences)."""
    sentences = re.split(r'(?<=[.!?])\s+', content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    
    if not sentences:
        return "Unable to extract summary."
    
    scored_sentences = []
    for sent in sentences[:20]:
        score = 0
        sent_lower = sent.lower()
        
        if any(w in sent_lower for w in ['found', 'discovered', 'revealed', 'showed', 'demonstrated']):
            score += 3
        if any(w in sent_lower for w in ['because', 'therefore', 'as a result', 'this means']):
            score += 2
        if any(w in sent_lower for w in ['problem', 'challenge', 'issue', 'crisis']):
            score += 2
        if any(w in sent_lower for w in ['solution', 'approach', 'method', 'strategy']):
            score += 2
        if re.search(r'\d+', sent):
            score += 1
        if len(sent) > 100:
            score += 1
        if len(sent) > 300:
            score -= 2
        
        scored_sentences.append((score, sent))
    
    scored_sentences.sort(reverse=True)
    top_sentences = [s for _, s in scored_sentences[:3]]
    
    # Reorder by original position for flow
    original_order = []
    for sent in sentences:
        if sent in top_sentences and len(original_order) < 2:
            original_order.append(sent)
    
    summary = ' '.join(original_order) if len(original_order) >= 2 else (original_order[0] if original_order else sentences[0])
    
    summary = re.sub(r'\s+', ' ', summary)
    if len(summary) > 400:
        summary = summary[:397] + '...'
    
    return summary


def analyze_significance(content: str, title: str) -> str:
    """Generate context-aware 'why this matters' for Alexander."""
    content_lower = content.lower()
    title_lower = title.lower()
    
    # More precise matching - avoid false positives
    significance_parts = []
    
    # Privacy/security - check title first (stronger signal)
    if any(w in title_lower for w in ['privacy', 'security', 'breach', 'tracking']):
        significance_parts.append("Privacy/security trend")
    elif any(phrase in content_lower[:2000] for phrase in ['privacy concerns', 'security vulnerability', 'data breach']):
        significance_parts.append("Privacy/security trend")
    
    # AI/ML - be careful not to match words inside other words
    ai_patterns = [' ai ', 'machine learning', 'llm ', 'language model', 'gpt-4', 'claude', 'neural network']
    if any(p in content_lower for p in ai_patterns):
        significance_parts.append("AI/ML development")
    
    # Infrastructure - specific terms
    infra_patterns = ['kubernetes', 'docker ', 'infrastructure', 'observability', 'database', 'cloud ', 'devops']
    if any(p in content_lower for p in infra_patterns):
        significance_parts.append("Infrastructure tooling")
    
    # Economics/business
    econ_patterns = ['startup', 'valuation', 'funding round', 'revenue', 'ipo ', 'market trend']
    if any(p in content_lower for p in econ_patterns):
        significance_parts.append("Market signal")
    
    # Open source
    oss_patterns = ['open source', 'github', ' open ', 'mit license', 'gpl license']
    if any(p in content_lower for p in oss_patterns):
        significance_parts.append("Open source ecosystem")
    
    # Research
    research_patterns = ['research paper', 'study found', 'published in', 'arxiv.org']
    if any(p in content_lower for p in research_patterns):
        significance_parts.append("Research finding")
    
    # Archives/preservation
    archive_patterns = ['internet archive', 'archive.org', 'digital preservation', 'library of congress']
    if any(p in content_lower for p in archive_patterns):
        significance_parts.append("Knowledge preservation issue")
    
    # Streaming/media (for Babylon 5 type stories)
    media_patterns = ['streaming', 'netflix', 'youtube', 'content licensing', 'media rights']
    if any(p in content_lower for p in media_patterns):
        significance_parts.append("Media/content landscape shift")
    
    # Software preservation/historical software
    preservation_patterns = ['reverse engineer', 'reverse-engineer', 'preservation', 'legacy code', 
                            '40 year old', '40-year-old', 'from 198', 'from 197', 'source code rescued',
                            'abandoned software', 'software archaeology']
    if any(p in title_lower or p in content_lower[:3000] for p in preservation_patterns):
        significance_parts.append("Software preservation")
    
    if significance_parts:
        if len(significance_parts) == 1:
            base = significance_parts[0]
        elif len(significance_parts) == 2:
            base = f"{significance_parts[0]} intersecting with {significance_parts[1]}"
        else:
            base = f"{significance_parts[0]} at the intersection of {significance_parts[1]} and {significance_parts[2]}"
        
        implications = {
            'Privacy/security trend': '— relevant to your infrastructure decisions and user trust.',
            'AI/ML development': '— may impact your tooling choices or the podcaster project.',
            'Infrastructure tooling': '— directly relevant to your DevOps work.',
            'Market signal': '— indicates where investment and talent are flowing.',
            'Open source ecosystem': '— affects sustainability of tools you depend on.',
            'Research finding': '— early signal of validated approaches.',
            'Knowledge preservation issue': '— affects long-term access to information.',
            'Media/content landscape shift': '— signals changes in how content is distributed and consumed.',
            'Software preservation': '— demonstrates techniques for maintaining access to legacy systems and code.',
        }
        
        for key, impl in implications.items():
            if key in base:
                return base + ' ' + impl
        
        return base + ' — worth tracking for implications to your work.'
    
    return 'Interesting development in your areas of focus — monitoring for emerging patterns.'


def synthesize_hn_discussion(story_id: int) -> Optional[str]:
    """Synthesize HN discussion themes - write in complete, coherent sentences."""
    try:
        resp = requests.get(
            f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
            timeout=10
        )
        story = resp.json()
        
        if not story or story.get('type') != 'story':
            return None
        
        comment_ids = story.get('kids', [])[:12]  # Top 12 comments
        
        comments = []
        for cid in comment_ids:
            try:
                cresp = requests.get(
                    f'https://hacker-news.firebaseio.com/v0/item/{cid}.json',
                    timeout=5
                )
                comment = cresp.json()
                
                if comment and comment.get('type') == 'comment':
                    text = comment.get('text', '')
                    text = re.sub(r'<[^>]+>', ' ', text).strip()
                    votes = comment.get('score', 0)
                    
                    # Skip comments that are too short or too long
                    if len(text) > 80 and len(text) < 900:
                        comments.append({'text': text, 'votes': votes})
            except Exception:
                continue
        
        if len(comments) < 3:
            return None
        
        # Identify themes from ALL comments
        all_text = ' '.join([c['text'].lower() for c in comments])
        
        themes = []
        theme_keywords = {
            'technical implementation': ['implementation', 'architecture', 'how it works', 'code quality'],
            'privacy concerns': ['privacy', 'tracking', 'data collection', 'surveillance'],
            'business model': ['revenue', 'business model', 'monetize', 'sustainable'],
            'alternatives': ['alternative', 'instead', 'competitor', 'better option'],
            'historical context': ['history', 'previously', 'used to', 'in the past'],
            'criticisms': ['issue', 'problem', 'concern', 'flaw', 'limitations'],
            'nostalgia/culture': ['nostalgia', 'classic', 'remember when', 'grew up with'],
            'quality assessment': ['quality', 'well made', 'holds up', 'aged well'],
        }
        
        for theme, keywords in theme_keywords.items():
            if any(kw in all_text for kw in keywords):
                themes.append(theme)
        
        # Score for insight quality
        def score_insight(c):
            text = c['text'].lower()
            score = 0
            
            # Experience-backed
            if any(p in text for p in ['i worked on', 'i built', 'we use', 'in production', 'at my company']):
                score += 10
            # Technical depth
            elif any(p in text for p in ['the issue is', 'the problem with', 'what actually happens']):
                score += 7
            # Historical
            elif any(p in text for p in ['this happened before', 'similar to', 'historically']):
                score += 6
            
            # Penalize short, reactive comments
            if len(c['text']) < 120:
                score -= 5
            
            return score
        
        comments.sort(key=score_insight, reverse=True)
        
        # Require at least one specific insight pattern
        insight_patterns = ['pointed out', 'noted that', 'argued that', 'explained that', 
                           'the key issue', 'the real problem', 'what matters', 'importantly',
                           'experience with', 'found that', 'discovered that']
        
        has_specific_insight = any(p in all_text for p in insight_patterns)
        
        # Build synthesis - use complete sentences only
        parts = []
        
        # Theme intro (only if we have specific insights)
        if themes and has_specific_insight:
            theme_str = ', '.join(themes[:2])
            parts.append(f"Commenters discussed {theme_str}.")
        
        # Best insight - extract complete, coherent thought with specific insight
        best_insight_added = False
        if comments and has_specific_insight:
            for comment in comments[:3]:  # Check top 3 for best insight
                text = comment['text']
                
                # Clean citations
                text = re.sub(r'\[\d+\]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Find a complete, substantive sentence with insight
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 50]
                
                for sent in sentences[:2]:
                    # Must contain insight indicator
                    if not any(p in sent.lower() for p in insight_patterns):
                        continue
                    
                    # Verify it's coherent
                    words = sent.lower().split()
                    has_subject = any(w in words for w in ['the', 'this', 'it', 'they', 'i', 'we', 'commenters'])
                    has_verb = any(w in words for w in ['is', 'are', 'was', 'were', 'shows', 'indicates', 'suggests', 'notes', 'explains'])
                    
                    if has_subject and has_verb and len(sent) < 350:
                        parts.append(sent)
                        best_insight_added = True
                        break
                
                if best_insight_added:
                    break
        
        # Sentiment (only if we have a substantive insight to pair with)
        if best_insight_added:
            positive_words = ['great', 'excellent', 'impressive', 'useful', 'helpful', 'good', 'well done']
            negative_words = ['problem', 'issue', 'concern', 'flaw', 'bad', 'disappointing', 'worried']
            
            pos_count = sum(1 for c in comments for w in positive_words if w in c['text'].lower())
            neg_count = sum(1 for c in comments for w in negative_words if w in c['text'].lower())
            
            if pos_count > neg_count + 1:
                parts.append("Overall reception was positive.")
            elif neg_count > pos_count + 1:
                parts.append("Significant concerns were raised.")
            else:
                parts.append("Mixed reactions with substantive debate.")
        
        if len(parts) >= 2:
            return ' '.join(parts)
        
        return None
                
    except Exception as e:
        return None


def extract_and_summarize(url: str, title: str, story_id: Optional[int] = None) -> ExtractedContent:
    """Main entry: extract content and create executive summary."""
    
    content = extract_article_content(url)
    
    if not content:
        return ExtractedContent(
            title=title,
            url=url,
            executive_summary=f"Unable to extract article content. Original title: {title}",
            significance="Source content unavailable — see original link.",
            hn_synthesis=None
        )
    
    exec_summary = synthesize_executive_summary(content, title)
    significance = analyze_significance(content, title)
    
    hn_synthesis = None
    if story_id:
        hn_synthesis = synthesize_hn_discussion(story_id)
    
    return ExtractedContent(
        title=title,
        url=url,
        executive_summary=exec_summary,
        significance=significance,
        hn_synthesis=hn_synthesis
    )
