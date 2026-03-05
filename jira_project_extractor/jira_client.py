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
            self.field_catalog = self._load_field_catalog()
            self.epic_link_field_id = self._find_field_id_by_label("Epic Link")
            logger.info("Initialized JIRA client for user %s", self.username)
        except Exception:
            logger.exception("Failed to initialize JIRA client")
            raise

    def _load_field_catalog(self) -> dict[str, str]:
        try:
            catalog: dict[str, str] = {}
            for field in self.client.fields():
                field_id = field.get("id")
                field_name = field.get("name")
                if field_id and field_name:
                    catalog[str(field_id)] = str(field_name)
            logger.info("Loaded %s JIRA field definitions", len(catalog))
            return catalog
        except Exception:
            logger.exception("Failed to load JIRA field catalog")
            return {}

    def _find_field_id_by_label(self, label: str) -> str | None:
        target = label.strip().lower()
        for field_id, field_name in self.field_catalog.items():
            if field_name.strip().lower() == target:
                return field_id
        return None

    def _issue_to_json(self, issue: Any) -> dict[str, Any]:
        raw = getattr(issue, "raw", None)
        if isinstance(raw, dict):
            result = dict(raw)
            result["__field_catalog"] = self.field_catalog
            result["__epic_link_field_id"] = self.epic_link_field_id
            return result
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
