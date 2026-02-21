import pytest
from morning_briefing.database import Database, Item
from morning_briefing.sources import HackerNewsSource, ArxivSource


class TestDatabase:
    def test_init_creates_tables(self, tmp_path):
        db = Database(tmp_path / "test.db")
        assert db.db_path.exists()
    
    def test_has_been_sent_false_for_new_url(self, tmp_path):
        db = Database(tmp_path / "test.db")
        assert not db.has_been_sent("https://example.com/new")
    
    def test_record_and_find_item(self, tmp_path):
        db = Database(tmp_path / "test.db")
        
        items = [
            Item(source="hn", title="Test", url="https://example.com/1", summary="Test summary")
        ]
        
        email_id = db.record_email("Test Subject", "to@test.com", tmp_path / "test.html", items)
        assert email_id == 1
        assert db.has_been_sent("https://example.com/1")


class TestHackerNewsSource:
    def test_fetch_top_stories(self):
        hn = HackerNewsSource()
        stories = hn.fetch_top_stories(limit=5)
        assert len(stories) <= 5
        assert all(hasattr(s, 'title') for s in stories)
    
    def test_filter_interesting(self):
        hn = HackerNewsSource()
        # Mock stories
        from morning_briefing.sources.hackernews import HNStory
        stories = [
            HNStory(id=1, title="Test", url="http://test.com", score=100, comments=20, top_comments=[]),
            HNStory(id=2, title="Low", url="http://low.com", score=5, comments=1, top_comments=[]),
        ]
        filtered = hn.filter_interesting(stories)
        assert len(filtered) == 1
        assert filtered[0].id == 1


class TestArxivSource:
    def test_fetch_recent(self):
        arxiv = ArxivSource()
        papers = arxiv.fetch_recent(days=1, max_per_cat=5)
        assert isinstance(papers, list)
    
    def test_calc_score(self):
        arxiv = ArxivSource()
        from morning_briefing.sources.arxiv import ArxivPaper
        
        paper = ArxivPaper(
            id="1234",
            title="Test",
            authors=["Author"],
            summary="Summary",
            url="http://arxiv.org/abs/1234",
            pdf_url="http://arxiv.org/pdf/1234",
            published="2024-01-01",
            categories=["cs.AI"],
            hn_mentioned=True,
            hn_points=150,
            github_repos=["github.com/user/repo"]
        )
        
        score = arxiv._calc_score(paper)
        assert score > 0
