"""Morning Briefing - Personalized news briefing system."""

__version__ = "0.1.0"

from .database import Database, Item
from .extractor import extract_and_summarize
from .email import format_story, generate_email

__all__ = [
    'Database',
    'Item', 
    'extract_and_summarize',
    'ExtractedContent',
    'format_story',
    'generate_email',
]
