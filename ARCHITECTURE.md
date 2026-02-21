# Morning Briefing Pipeline Architecture

## Alexander's Proposed 3-Stage Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. SELECTION   │────▶│  2. SUMMARIZE   │────▶│ 3. ASSEMBLY     │
│   (Wide funnel) │     │  (Generate many)│     │ (Filter to best)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Current Implementation (Mixed stages)

```
HN Fetch ──▶ Filter by score ──▶ Extract content ──▶ Build email
     │              │                  │
     └──────────────┴──────────────────┘
           (All happens in one loop)
```

**Problems with current approach:**
- Can't judge summary quality before deciding to include
- No opportunity to swap in better items if extraction fails
- HN extraction happens inline, can't retry or compare alternatives

## Target Architecture

### Stage 1: Selection (Wide funnel)
```python
candidates = []

# HN: Top 50 stories
candidates += fetch_hn(limit=50, min_score=20)

# arXiv: More papers
candidates += fetch_arxiv(days=7, limit_per_cat=20)

# Web search: Fill gaps if needed
candidates += search_news(query="tech AI infrastructure", limit=10)

# Deduplicate against DB
# Score by potential (HN points, traction, relevance keywords)
# Sort by potential score
candidates = rank_by_potential(candidates)[:15]  # Keep top 15
```

### Stage 2: Summarize (Generate many)
```python
summarized = []

for item in candidates:
    try:
        summary = extract_and_summarize(item.url, item.title)
        
        # Quality scoring
        quality_score = assess_quality(summary)
        # - Executive summary coherence
        # - Significance accuracy
        # - HN synthesis specificity
        # - Content extraction success
        
        summarized.append({
            'item': item,
            'summary': summary,
            'quality_score': quality_score,
            'extraction_success': True
        })
    except:
        summarized.append({
            'item': item,
            'extraction_success': False,
            'quality_score': 0
        })

# Sort by quality
summarized.sort(key=lambda x: x['quality_score'], reverse=True)
```

### Stage 3: Assembly (Filter to best)
```python
# Target: 3-5 high-quality stories
selected = []

for s in summarized:
    if s['quality_score'] < 0.6:  # Minimum quality threshold
        continue
    if len(selected) >= 5:
        break
    selected.append(s)

# If we don't have enough quality stories, fall back or skip email
if len(selected) < 3:
    # Option A: Lower threshold
    # Option B: Don't send (better than low-quality)
    # Option C: Include brief note about light news day

# Build email from selected
email_html = assemble_email(selected)
```

## Benefits

1. **Quality-based filtering**: Can reject poor summaries even if original story seemed promising

2. **Flexibility**: If HN extraction fails for top story, #6 is already summarized and ready

3. **Testing**: Can run Stage 2 on many items and review quality before Stage 3

4. **Transparency**: Can report "15 candidates → 12 extracted → 4 high quality" in logs

5. **Fallbacks**: Multiple sources feeding one pipeline, easy to add mailing lists, RSS, etc.

## Implementation Plan

### Phase 1: Refactor to 3-stage (today)
- Separate selection from summarization
- Add quality scoring
- Assembly picks best N

### Phase 2: Add sources (next)
- RSS feeds (Techmeme, The Information)
- Mailing lists (via IMAP)
- Twitter/X lists (if API access)

### Phase 3: Smart filtering (later)
- ML-based relevance scoring from feedback
- Topic clustering (don't send 3 AI stories)
- Diversity injection (if all tech, add one econ)

## Quality Metrics to Track

```python
class QualityScore:
    extraction_success: bool      # Did we get content?
    summary_coherence: float      # 0-1, sentence flow
    summary_completeness: float   # 0-1, did we capture main point?
    significance_accuracy: float  # 0-1, correct category?
    hn_quality: float            # 0-1, synthesis vs generic?
    
    @property
    def overall(self) -> float:
        if not self.extraction_success:
            return 0
        return (self.summary_coherence * 0.3 + 
                self.significance_accuracy * 0.3 +
                self.hn_quality * 0.2 +
                self.summary_completeness * 0.2)
```

## Current Blockers for Implementation

1. HN synthesis still produces generic output
2. Significance detection needs more test cases
3. Need quality scoring implementation

## Decision: Refactor or Fix-in-Place?

**Option A: Refactor now**
- Pro: Clean architecture, easier to extend
- Con: More code change, longer to working state

**Option B: Fix current, then refactor**
- Pro: Get working emails sooner
- Con: Technical debt, harder to fix synthesis in current structure

**Recommendation**: Refactor to 3-stage now while we're paused. The architecture enables better quality control, which is the core problem.
