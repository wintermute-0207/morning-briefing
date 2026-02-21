# Morning Briefing

Personalized morning news briefing system with traction-based content ranking and feedback-driven iteration.

## Features

- **Multi-source aggregation**: Hacker News, arXiv, mailing lists, web search
- **Traction-based ranking**: Composite scoring from HN mentions, citations, GitHub repos
- **Deduplication**: Tracks what's been sent to avoid repeats
- **Feedback tracking**: Rate items 1-5 stars + comments to improve curation
- **Styled HTML emails**: Clean, mobile-responsive templates
- **CLI interface**: Simple commands for management and feedback

## Installation

```bash
cd morning-briefing
pip install -e .
```

## Configuration

Create `~/.config/morning-briefing/config.json`:

```json
{
  "email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "from": "your-email@gmail.com",
    "to": "recipient@example.com"
  },
  "interests": ["tech", "economics", "science", "f1"],
  "sources": {
    "hackernews": {"enabled": true, "max_stories": 4},
    "arxiv": {"enabled": true, "categories": ["cs.AI", "cs.SE", "econ.GN"]},
    "mailing_lists": {"enabled": true, "check_email": "your-email@gmail.com"}
  }
}
```

## Usage

### Generate and send briefing

```bash
mbrief generate --send
```

### View recent emails

```bash
mbrief list --limit 10
```

### Provide feedback

```bash
# Rate by item ID
mbrief feedback 42 --rating 5 --comment "Exactly what I needed"

# Rate by URL
mbrief feedback https://arxiv.org/abs/1234 --rating 3
```

### View statistics

```bash
mbrief stats              # Aggregate feedback by source
mbrief top --min-rating 4 # Top-rated items
```

### Check if URL was already sent

```bash
mbrief sent https://example.com/article
```

## Data Storage

- SQLite database: `~/.local/share/morning-briefing/briefing.db`
- Sent emails archived: `~/.local/share/morning-briefing/emails/`

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src/
```

## License

MIT

## Content Pipeline Overview

```mermaid
graph TD
    subgraph "Sources"
        HN_API["HN Firebase API"]
        ARXIV_API["arXiv API"]
        HN_ALGOLIA["HN Algolia API"]
        SS_API["Semantic Scholar API"]
    end

    subgraph "Stage 1: Selection"
        HN_FETCH["HackerNewsSource.fetch_top_stories\n(limit=50)"]
        HN_FILTER["filter_interesting\n(min_score=20)"]
        HN_CAT["Categorize\n(tech, economics, science, f1)"]
        ARXIV_FETCH["ArxivSource.fetch_recent\n(days=7, max_per_cat=20)"]
        ARXIV_DEDUP["Deduplicate papers"]
        DB_DEDUP["Database.has_been_sent\n(URL dedup)"]
        SCORE_HN["_hn_potential\n(score + comments + ratio)"]
        SCORE_ARXIV["_arxiv_potential\n(traction + github)"]
        RANK["Rank by potential_score\nKeep top 15"]
    end

    subgraph "Stage 2: Summarize"
        EXTRACT["extract_article_content\n(trafilatura / regex fallback)"]
        EXEC_SUMMARY["synthesize_executive_summary\n(sentence scoring)"]
        SIGNIFICANCE["analyze_significance\n(category detection + implication)"]
        HN_SYNTH["synthesize_hn_discussion\n(theme + insight extraction)"]
        ARXIV_SUMMARY["arXiv abstract truncation\n(first 400 chars)"]
        QUALITY["assess_quality"]
        Q_COHERENCE["score_summary_coherence"]
        Q_COMPLETE["score_summary_completeness"]
        Q_SIGNIF["score_significance_accuracy"]
        Q_HN["score_hn_synthesis"]
        SORT_QUALITY["Sort by quality_score"]
    end

    subgraph "Stage 3: Assembly"
        FILTER_Q["Filter quality >= 0.6\nMax 5 items"]
        MIN_CHECK{">= 3 items?"}
        SKIP["Skip email\n(quality > quantity)"]
        FORMAT["format_story\n(per-item HTML)"]
        GEN_EMAIL["generate_email\n(HTML template)"]
        SAVE["save_email\n(date-stamped .html)"]
    end

    subgraph "Delivery"
        SEND{"Send?"}
        SENDGRID["SendGrid API"]
        SMTP["SMTP via curl"]
        RECORD_DB["Database.record_email\n+ items"]
    end

    subgraph "Feedback Loop"
        FB_IN["mbrief feedback\n(rating 1-5 + comment)"]
        FB_DB["feedback table"]
        FB_STATS["mbrief stats / top"]
    end

    HN_API --> HN_FETCH
    HN_FETCH --> HN_FILTER
    HN_FILTER --> HN_CAT
    HN_CAT --> DB_DEDUP

    ARXIV_API --> ARXIV_FETCH
    ARXIV_FETCH --> ARXIV_DEDUP
    ARXIV_DEDUP --> DB_DEDUP

    DB_DEDUP --> SCORE_HN
    DB_DEDUP --> SCORE_ARXIV
    SCORE_HN --> RANK
    SCORE_ARXIV --> RANK

    RANK -->|"HN candidates"| EXTRACT
    RANK -->|"arXiv candidates"| ARXIV_SUMMARY

    EXTRACT --> EXEC_SUMMARY
    EXEC_SUMMARY --> SIGNIFICANCE
    SIGNIFICANCE --> HN_SYNTH
    HN_API --> HN_SYNTH

    ARXIV_SUMMARY --> QUALITY
    HN_SYNTH --> QUALITY

    QUALITY --> Q_COHERENCE
    QUALITY --> Q_COMPLETE
    QUALITY --> Q_SIGNIF
    QUALITY --> Q_HN
    Q_COHERENCE --> SORT_QUALITY
    Q_COMPLETE --> SORT_QUALITY
    Q_SIGNIF --> SORT_QUALITY
    Q_HN --> SORT_QUALITY

    SORT_QUALITY --> FILTER_Q
    FILTER_Q --> MIN_CHECK
    MIN_CHECK -->|No| SKIP
    MIN_CHECK -->|Yes| FORMAT
    FORMAT --> GEN_EMAIL
    GEN_EMAIL --> SAVE

    SAVE --> SEND
    SEND -->|"--send flag"| SENDGRID
    SEND -->|"--send flag"| SMTP
    SEND -->|"no flag"| RECORD_DB
    SENDGRID --> RECORD_DB
    SMTP --> RECORD_DB

    RECORD_DB --> FB_IN
    FB_IN --> FB_DB
    FB_DB --> FB_STATS

    HN_ALGOLIA -.-> ARXIV_FETCH
    SS_API -.-> ARXIV_FETCH
```