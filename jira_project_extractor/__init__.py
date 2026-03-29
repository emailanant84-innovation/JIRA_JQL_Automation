"""JIRA project extraction and normalization package."""

from .logging_utils import configure_logging
from .orchestrator import JiraExtractionOrchestrator

configure_logging()

__all__ = ["JiraExtractionOrchestrator", "configure_logging"]
