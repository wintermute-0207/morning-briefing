"""arXiv source with traction-based ranking."""

import requests
import xml.etree.ElementTree as ET
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ArxivPaper:
    """An arXiv paper with traction signals."""
    id: str
    title: str
    authors: list[str]
    summary: str
    url: str
    pdf_url: str
    published: str
    categories: list[str]
    
    # Traction signals
    hn_mentioned: bool = False
    hn_points: int = 0
    hn_url: str = ""
    
    ss_influential_citations: int = 0
    ss_total_citations: int = 0
    
    github_repos: list[str] = None
    
    traction_score: float = 0.0
    
    def __post_init__(self):
        if self.github_repos is None:
            self.github_repos = []


class ArxivSource:
    """Fetch and rank arXiv papers by traction."""
    
    # Categories relevant to Alexander
    CATEGORIES = ['cs.AI', 'cs.SE', 'cs.CL', 'cs.CY', 'econ.GN', 'econ.TH', 'q-fin.EC']
    
    # Signal weights for composite score
    WEIGHTS = {
        'hn_mentions': 30,
        'github_links': 20,
        'ss_influential': 25,
        'recency': 10,
    }
    
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_recent(self, days: int = 5, max_per_cat: int = 20) -> list[ArxivPaper]:
        """Fetch recent papers from relevant categories."""
        papers = []
        
        for cat in self.CATEGORIES:
            url = f'http://export.arxiv.org/api/query?search_query=cat:{cat}&start=0&max_results={max_per_cat}&sortBy=submittedDate&sortOrder=descending'
            
            try:
                resp = self.session.get(url, timeout=30)
                root = ET.fromstring(resp.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                for entry in root.findall('.//atom:entry', ns):
                    paper = self._parse_entry(entry, ns)
                    if paper:
                        # Filter by date
                        pub = datetime.strptime(paper.published, '%Y-%m-%d')
                        if pub >= datetime.now() - timedelta(days=days):
                            papers.append(paper)
                
                time.sleep(0.5)  # Rate limit
                
            except Exception as e:
                print(f"Error fetching {cat}: {e}")
                continue
        
        # Deduplicate
        seen = set()
        unique = []
        for p in papers:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)
        
        return unique
    
    def _parse_entry(self, entry, ns) -> Optional[ArxivPaper]:
        """Parse an arXiv entry."""
        try:
            id_elem = entry.find('atom:id', ns)
            arxiv_id = id_elem.text.split('/')[-1].split('v')[0]
            
            pdf_link = entry.find('atom:link[@title="pdf"]', ns)
            
            return ArxivPaper(
                id=arxiv_id,
                title=entry.find('atom:title', ns).text.replace('\n', ' ').strip(),
                authors=[a.find('atom:name', ns).text 
                        for a in entry.findall('atom:author', ns)],
                summary=entry.find('atom:summary', ns).text.replace('\n', ' ').strip()[:500],
                url=entry.find('atom:link[@rel="alternate"]', ns).get('href'),
                pdf_url=pdf_link.get('href') if pdf_link else None,
                published=entry.find('atom:published', ns).text[:10],
                categories=[c.get('term') for c in entry.findall('atom:category', ns)]
            )
        except Exception:
            return None
    
    def enrich_with_traction(self, papers: list[ArxivPaper]) -> list[ArxivPaper]:
        """Add traction signals to papers."""
        for paper in papers:
            # Check HN
            hn = self._check_hn(paper.id)
            if hn:
                paper.hn_mentioned = True
                paper.hn_points = hn.get('points', 0)
                paper.hn_url = hn.get('url', '')
            
            # Check Semantic Scholar
            ss = self._check_semantic_scholar(paper.id)
            if ss:
                paper.ss_influential_citations = ss.get('influential_citations', 0)
                paper.ss_total_citations = ss.get('total_citations', 0)
            
            # Check for GitHub repos in abstract
            repos = re.findall(r'github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', 
                             paper.summary)
            paper.github_repos = repos
            
            # Calculate traction score
            paper.traction_score = self._calc_score(paper)
            
            time.sleep(0.2)
        
        return papers
    
    def _check_hn(self, arxiv_id: str) -> Optional[dict]:
        """Check if paper was mentioned on HN."""
        try:
            url = f'https://hn.algolia.com/api/v1/search?query=arxiv.org/abs/{arxiv_id}&tags=story'
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            
            if data['hits']:
                hit = max(data['hits'], key=lambda x: x.get('points', 0))
                return {
                    'points': hit.get('points', 0),
                    'url': f"https://news.ycombinator.com/item?id={hit['objectID']}"
                }
            return None
        except Exception:
            return None
    
    def _check_semantic_scholar(self, arxiv_id: str) -> Optional[dict]:
        """Get citation data from Semantic Scholar."""
        try:
            url = f'https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields=influentialCitationCount,citationCount'
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'influential_citations': data.get('influentialCitationCount', 0),
                    'total_citations': data.get('citationCount', 0)
                }
            return None
        except Exception:
            return None
    
    def _calc_score(self, paper: ArxivPaper) -> float:
        """Calculate composite traction score."""
        score = 0.0
        
        if paper.hn_mentioned:
            score += self.WEIGHTS['hn_mentions'] * min(paper.hn_points / 100, 2)
        
        if paper.github_repos:
            score += self.WEIGHTS['github_links'] * min(len(paper.github_repos), 2)
        
        if paper.ss_influential_citations:
            score += self.WEIGHTS['ss_influential'] * min(paper.ss_influential_citations / 5, 2)
        
        # Recency boost
        pub = datetime.strptime(paper.published, '%Y-%m-%d')
        if (datetime.now() - pub).days <= 3:
            score += self.WEIGHTS['recency']
        
        return round(score, 2)
    
    def get_top_papers(self, papers: list[ArxivPaper], limit: int = 5) -> list[ArxivPaper]:
        """Get top papers by traction score."""
        enriched = self.enrich_with_traction(papers)
        return sorted(enriched, key=lambda x: x.traction_score, reverse=True)[:limit]
