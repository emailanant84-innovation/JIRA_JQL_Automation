from __future__ import annotations

from typing import Any

from jira import JIRA

from .config import JiraConfig
from .logging_utils import get_logger

logger = get_logger("jira_client")


class JiraApiClient:
    """JIRA client using username/password authentication and corporate cert verification."""

    def __init__(self, config: JiraConfig) -> None:
        try:
            self.config = config
            self.username = config.resolved_username()
            self.client = JIRA(
                server=config.base_url,
                basic_auth=(self.username, config.password),
                options={"verify": config.resolved_verify_cert_path()},
            )
            logger.info("Initialized JIRA client for user %s", self.username)
        except Exception:
            logger.exception("Failed to initialize JIRA client")
            raise

    @staticmethod
    def _issue_to_json(issue: Any) -> dict[str, Any]:
        raw = getattr(issue, "raw", None)
        if isinstance(raw, dict):
            return raw
        raise ValueError("Unexpected issue payload returned by JIRA client.")

    def search_issues(
        self,
        jql: str,
        fields: list[str],
        expand: list[str] | None = None,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            start_at = 0
            collected: list[dict[str, Any]] = []
            logger.info("Starting JIRA search with JQL: %s", jql)

            while True:
                issues = self.client.search_issues(
                    jql_str=jql,
                    startAt=start_at,
                    maxResults=batch_size,
                    fields=fields,
                    expand=",".join(expand or []),
                )
                chunk = [self._issue_to_json(issue) for issue in issues]
                collected.extend(chunk)
                if len(chunk) < batch_size:
                    break
                start_at += len(chunk)

            logger.info("Fetched %s issues from search", len(collected))
            return collected
        except Exception:
            logger.exception("Failed during search_issues")
            raise

    def get_issue(self, issue_key: str, fields: list[str]) -> dict[str, Any]:
        try:
            issue = self.client.issue(
                id=issue_key,
                fields=",".join(fields),
                expand="renderedFields",
            )
            return self._issue_to_json(issue)
        except Exception:
            logger.exception("Failed to fetch issue %s", issue_key)
            raise
