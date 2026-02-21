"""3-stage pipeline: Selection -> Summarize -> Assembly."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .database import Database, Item
from .sources import HackerNewsSource, ArxivSource, HNStory, ArxivPaper
from .extractor import extract_and_summarize, ExtractedContent
from .email import format_story, generate_email, save_email
from .quality import assess_quality, QualityScore


# ---------------------------------------------------------------------------
# Data containers passed between stages
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A candidate item from Stage 1 (selection)."""
    source: str          # 'hn' or 'arxiv'
    title: str
    url: str
    potential_score: float
    # HN-specific
    hn_id: Optional[int] = None
    hn_score: int = 0
    hn_comments: int = 0
    category: str = "tech"
    # arXiv-specific
    arxiv_id: str = ""
    arxiv_authors: list = field(default_factory=list)
    arxiv_summary: str = ""
    traction_score: float = 0.0
    github_repos: list = field(default_factory=list)
    hn_mentioned: bool = False


@dataclass
class SummarizedItem:
    """A candidate after Stage 2 (summarization + quality scoring)."""
    candidate: Candidate
    extraction_success: bool
    executive_summary: str = ""
    significance: str = ""
    hn_synthesis: Optional[str] = None
    quality: Optional[QualityScore] = None

    @property
    def quality_score(self) -> float:
        return self.quality.overall if self.quality else 0.0


@dataclass
class PipelineResult:
    """Final output from the pipeline."""
    candidates_found: int
    candidates_summarized: int
    items_selected: int
    html_path: Optional[Path] = None
    skipped_reason: Optional[str] = None
    selected: list = field(default_factory=list)  # list[SummarizedItem]


# ---------------------------------------------------------------------------
# Stage 1: Selection (wide funnel)
# ---------------------------------------------------------------------------

def select_candidates(config: dict, db: Database) -> list[Candidate]:
    """Fetch from all sources, deduplicate, score by potential, keep top 15."""
    candidates = []

    # --- HN ---
    if config.get('sources', {}).get('hackernews', {}).get('enabled', True):
        print("Stage 1: Fetching Hacker News...")
        hn = HackerNewsSource()
        stories = hn.fetch_top_stories(limit=50)
        filtered = hn.filter_interesting(stories, min_score=20)

        for story in filtered:
            if db.has_been_sent(story.url):
                continue
            candidates.append(Candidate(
                source='hn',
                title=story.title,
                url=story.url,
                hn_id=story.id,
                hn_score=story.score,
                hn_comments=story.comments,
                category=story.category,
                potential_score=_hn_potential(story),
            ))

    # --- arXiv ---
    if config.get('sources', {}).get('arxiv', {}).get('enabled', True):
        print("Stage 1: Fetching arXiv...")
        arxiv = ArxivSource()
        papers = arxiv.fetch_recent(days=7, max_per_cat=20)

        for paper in papers:
            if db.has_been_sent(paper.url):
                continue

            traction = 0.0
            if paper.hn_mentioned:
                traction += 30
            if paper.github_repos:
                traction += 20

            candidates.append(Candidate(
                source='arxiv',
                title=paper.title,
                url=paper.url,
                arxiv_id=paper.id,
                arxiv_authors=paper.authors[:3],
                arxiv_summary=paper.summary,
                traction_score=traction,
                github_repos=paper.github_repos or [],
                hn_mentioned=paper.hn_mentioned,
                category='research',
                potential_score=_arxiv_potential(paper, traction),
            ))

    # Sort by potential, keep top 15
    candidates.sort(key=lambda c: c.potential_score, reverse=True)
    top = candidates[:15]

    print(f"Stage 1: {len(candidates)} candidates after dedup -> keeping top {len(top)}")
    return top


def _hn_potential(story: HNStory) -> float:
    """Score an HN story's potential (higher = more promising)."""
    score = 0.0
    # Raw engagement
    score += min(story.score / 50, 3.0) * 20   # Up to 60 from score
    score += min(story.comments / 50, 2.0) * 10  # Up to 20 from comments
    # Engagement ratio (comments per point = controversy/interest)
    if story.score > 0:
        ratio = story.comments / story.score
        score += min(ratio, 1.0) * 10
    return round(score, 2)


def _arxiv_potential(paper: ArxivPaper, traction: float) -> float:
    """Score an arXiv paper's potential."""
    score = traction  # Base from traction signals
    if paper.github_repos:
        score += 10  # Implementation available
    return round(score, 2)


# ---------------------------------------------------------------------------
# Stage 2: Summarize (generate many)
# ---------------------------------------------------------------------------

def summarize_candidates(candidates: list[Candidate]) -> list[SummarizedItem]:
    """Extract content and generate summaries for each candidate."""
    results = []

    for i, cand in enumerate(candidates, 1):
        print(f"Stage 2: [{i}/{len(candidates)}] {cand.title[:55]}...")

        if cand.source == 'hn':
            result = _summarize_hn(cand)
        elif cand.source == 'arxiv':
            result = _summarize_arxiv(cand)
        else:
            continue

        # Score quality
        result.quality = assess_quality(
            summary=result.executive_summary,
            title=cand.title,
            significance=result.significance,
            source=cand.source,
            url=cand.url,
            hn_synthesis=result.hn_synthesis,
            extraction_success=result.extraction_success,
        )

        status = f"q={result.quality_score:.2f}"
        if not result.extraction_success:
            status = "extraction failed"
        print(f"         {status}")

        results.append(result)

    # Sort by quality
    results.sort(key=lambda r: r.quality_score, reverse=True)
    return results


def _summarize_hn(cand: Candidate) -> SummarizedItem:
    """Summarize a Hacker News candidate."""
    extracted = extract_and_summarize(cand.url, cand.title, cand.hn_id)

    extraction_ok = not extracted.executive_summary.startswith("Unable to extract")
    return SummarizedItem(
        candidate=cand,
        extraction_success=extraction_ok,
        executive_summary=extracted.executive_summary,
        significance=extracted.significance,
        hn_synthesis=extracted.hn_synthesis,
    )


def _summarize_arxiv(cand: Candidate) -> SummarizedItem:
    """Summarize an arXiv candidate (uses abstract directly)."""
    exec_summary = cand.arxiv_summary[:400]
    if len(cand.arxiv_summary) > 400:
        exec_summary += "..."

    significance = f"Recent research in {cand.category}"
    if cand.github_repos:
        significance += " with available implementation"
    significance += " — potential relevance to technical work."

    return SummarizedItem(
        candidate=cand,
        extraction_success=True,
        executive_summary=exec_summary,
        significance=significance,
        hn_synthesis=None,
    )


# ---------------------------------------------------------------------------
# Stage 3: Assembly (filter to best)
# ---------------------------------------------------------------------------

MIN_QUALITY = 0.6
MIN_ITEMS = 3
MAX_ITEMS = 5


def assemble_briefing(summarized: list[SummarizedItem],
                      output_dir: Path) -> PipelineResult:
    """Filter by quality, build HTML email if enough items pass."""
    total_candidates = len(summarized)

    # Filter by quality threshold
    selected = [s for s in summarized if s.quality_score >= MIN_QUALITY][:MAX_ITEMS]

    print(f"Stage 3: {total_candidates} summarized -> {len(selected)} above quality {MIN_QUALITY}")
    for s in selected:
        print(f"  [{s.quality_score:.2f}] {s.candidate.title[:60]}")

    if len(selected) < MIN_ITEMS:
        reason = (f"Only {len(selected)} items met quality threshold "
                  f"(need {MIN_ITEMS}). Skipping email — quality > quantity.")
        print(f"Stage 3: {reason}")
        return PipelineResult(
            candidates_found=total_candidates,
            candidates_summarized=sum(1 for s in summarized if s.extraction_success),
            items_selected=len(selected),
            skipped_reason=reason,
            selected=selected,
        )

    # Build HTML
    stories_html = []
    for s in selected:
        stories_html.append(format_story(
            title=s.candidate.title,
            url=s.candidate.url,
            executive_summary=s.executive_summary,
            significance=s.significance,
            source=s.candidate.source,
            category=s.candidate.category,
            hn_synthesis=s.hn_synthesis,
        ))

    html = generate_email(stories_html)
    html_path = save_email(html, output_dir)

    return PipelineResult(
        candidates_found=total_candidates,
        candidates_summarized=sum(1 for s in summarized if s.extraction_success),
        items_selected=len(selected),
        html_path=html_path,
        selected=selected,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_pipeline(config: dict, db: Database,
                 output_dir: Path) -> PipelineResult:
    """Run the full 3-stage pipeline."""
    print("=" * 60)
    print("Morning Briefing Pipeline")
    print("=" * 60)

    # Stage 1
    candidates = select_candidates(config, db)
    if not candidates:
        print("No candidates found. Nothing to do.")
        return PipelineResult(
            candidates_found=0, candidates_summarized=0, items_selected=0,
            skipped_reason="No candidates found from any source.",
        )

    # Stage 2
    summarized = summarize_candidates(candidates)

    # Stage 3
    result = assemble_briefing(summarized, output_dir)

    print("=" * 60)
    print(f"Pipeline complete: {result.candidates_found} candidates "
          f"-> {result.candidates_summarized} summarized "
          f"-> {result.items_selected} selected")
    if result.html_path:
        print(f"Email saved: {result.html_path}")
    elif result.skipped_reason:
        print(f"Email skipped: {result.skipped_reason}")
    print("=" * 60)

    return result


def items_from_result(result: PipelineResult) -> list[Item]:
    """Convert pipeline result to database Item objects for recording."""
    items = []
    for s in result.selected:
        c = s.candidate
        items.append(Item(
            source=c.source,
            source_id=c.arxiv_id or str(c.hn_id or ''),
            title=c.title,
            url=c.url,
            summary=s.executive_summary,
            category=c.category,
            hn_points=c.hn_score,
            hn_comments=c.hn_comments,
            traction_score=c.traction_score,
            arxiv_authors=c.arxiv_authors,
        ))
    return items
