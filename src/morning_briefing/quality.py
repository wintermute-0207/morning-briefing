"""Quality scoring for briefing item summaries."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityScore:
    """Quality assessment for a summarized item."""
    extraction_success: bool
    summary_coherence: float      # 0-1, sentence flow and readability
    summary_completeness: float   # 0-1, captures main point
    significance_accuracy: float  # 0-1, correct category detection
    hn_quality: float             # 0-1, synthesis vs generic (0 if no HN data)

    @property
    def overall(self) -> float:
        if not self.extraction_success:
            return 0.0
        return (self.summary_coherence * 0.3 +
                self.significance_accuracy * 0.3 +
                self.hn_quality * 0.2 +
                self.summary_completeness * 0.2)


def score_summary_coherence(summary: str) -> float:
    """Score how coherent and readable a summary is (0-1)."""
    if not summary or summary.startswith("Unable to extract"):
        return 0.0

    score = 0.0

    # Has multiple sentences (good narrative flow)
    sentences = re.split(r'(?<=[.!?])\s+', summary)
    sentences = [s for s in sentences if len(s.strip()) > 10]
    if len(sentences) >= 2:
        score += 0.3
    elif len(sentences) == 1:
        score += 0.15

    # Reasonable length (not too short, not truncated)
    if 80 <= len(summary) <= 400:
        score += 0.25
    elif len(summary) > 400:
        score += 0.1  # Truncated, but has content

    # Doesn't end mid-sentence (truncation artifact)
    if summary.rstrip().endswith(('.', '!', '?', '..."')):
        score += 0.15
    elif summary.endswith('...'):
        score += 0.05  # Truncated but marked

    # Contains substantive words (not just filler)
    substantive = ['found', 'shows', 'enables', 'introduces', 'built',
                    'developed', 'research', 'approach', 'system', 'method',
                    'results', 'performance', 'users', 'data', 'model']
    matches = sum(1 for w in substantive if w in summary.lower())
    score += min(matches * 0.05, 0.2)

    # No HTML artifacts
    if '<' not in summary and '&amp;' not in summary:
        score += 0.1

    return min(score, 1.0)


def score_summary_completeness(summary: str, title: str, url: str = "") -> float:
    """Score whether the summary captures the main point of the article (0-1)."""
    if not summary or summary.startswith("Unable to extract"):
        return 0.0

    score = 0.0
    summary_lower = summary.lower()
    title_lower = title.lower()

    # Title keywords appear in summary (summary is about the right topic)
    title_words = [w for w in re.findall(r'\w+', title_lower) if len(w) > 3]
    if title_words:
        overlap = sum(1 for w in title_words if w in summary_lower)
        score += min(overlap / len(title_words), 1.0) * 0.4
    
    # Check if URL domain keywords appear in summary (content validation)
    if url:
        domain = url.split('/')[2] if '/' in url else ""
        domain_keywords = domain.replace('.', ' ').replace('-', ' ').split()
        domain_keywords = [k for k in domain_keywords if len(k) > 3 and k not in ['github', 'com', 'www', 'blog']]
        if domain_keywords:
            domain_overlap = sum(1 for k in domain_keywords if k in summary_lower)
            score += min(domain_overlap / len(domain_keywords), 1.0) * 0.15

    # Has explanatory content (not just restating the title)
    if len(summary) > len(title) * 1.5:
        score += 0.3

    # Contains causal/explanatory language
    explanatory = ['because', 'by', 'through', 'using', 'which', 'that',
                   'allows', 'enables', 'means', 'results']
    if any(w in summary_lower for w in explanatory):
        score += 0.2

    # Has specific details (numbers, names, technical terms)
    if re.search(r'\d+', summary):
        score += 0.1
    
    # PENALTY: Content that doesn't match title (likely bad extraction)
    # If title is about "Babylon 5" but summary talks about "trade paperback"
    if title_words and len(title_words) >= 2:
        key_terms = title_words[:3]  # Top 3 words from title
        key_matches = sum(1 for w in key_terms if w in summary_lower)
        if key_matches == 0:
            # Summary has none of the key terms from title - likely wrong content
            score = max(0, score - 0.5)

    return min(score, 1.0)


def score_significance_accuracy(significance: str, title: str, source: str) -> float:
    """Score whether the significance field is accurate and specific (0-1)."""
    if not significance:
        return 0.0

    score = 0.0
    sig_lower = significance.lower()

    # Not the generic fallback
    if 'monitoring for emerging patterns' not in sig_lower:
        score += 0.3
    else:
        return 0.15  # Generic fallback gets minimal score

    # Has a specific category identified
    categories = ['privacy', 'security', 'ai/ml', 'infrastructure',
                  'market', 'open source', 'research', 'preservation', 'media']
    if any(c in sig_lower for c in categories):
        score += 0.3

    # Has implication for the reader (personalized)
    if any(w in sig_lower for w in ['your', 'relevant', 'impact', 'affects']):
        score += 0.2

    # Reasonable length (not too terse, not too verbose)
    if 30 <= len(significance) <= 200:
        score += 0.2

    return min(score, 1.0)


def score_hn_synthesis(hn_synthesis: Optional[str]) -> float:
    """Score HN discussion synthesis quality (0-1). Returns 0.5 if no HN data."""
    if hn_synthesis is None:
        return 0.5  # Neutral — don't penalize non-HN items

    if not hn_synthesis:
        return 0.0

    score = 0.0
    hn_lower = hn_synthesis.lower()

    # Has identified themes
    if 'discussed' in hn_lower or 'debate' in hn_lower or 'commenters' in hn_lower:
        score += 0.2

    # Has specific insight (not just "people talked about it")
    insight_signals = ['pointed out', 'noted', 'argued', 'explained',
                       'experience', 'production', 'worked on', 'built']
    if any(s in hn_lower for s in insight_signals):
        score += 0.25

    # Multiple sentences (richer synthesis)
    sentences = re.split(r'(?<=[.!?])\s+', hn_synthesis)
    if len(sentences) >= 2:
        score += 0.2

    # Has sentiment summary
    if any(w in hn_lower for w in ['positive', 'negative', 'mixed', 'concerns', 'enthusiasm']):
        score += 0.15

    # Reasonable length
    if 50 <= len(hn_synthesis) <= 400:
        score += 0.2

    return min(score, 1.0)


def assess_quality(summary: str, title: str, significance: str,
                   source: str, url: str = "", hn_synthesis: Optional[str] = None,
                   extraction_success: bool = True) -> QualityScore:
    """Assess overall quality of a summarized item."""
    return QualityScore(
        extraction_success=extraction_success,
        summary_coherence=score_summary_coherence(summary),
        summary_completeness=score_summary_completeness(summary, title, url),
        significance_accuracy=score_significance_accuracy(significance, title, source),
        hn_quality=score_hn_synthesis(hn_synthesis),
    )
