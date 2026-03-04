from __future__ import annotations

from typing import Any

import requests

from .config import JiraConfig


class JiraApiClient:
    """Low-level JIRA API client with pagination support."""

    def __init__(self, config: JiraConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.email, config.api_token)
        self.session.headers.update({"Accept": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.config.normalized_base_url()}{path}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            self._url(path),
            params=params,
            timeout=60,
            verify=self.config.verify_ssl,
        )
        response.raise_for_status()
        return response.json()

    def search_issues(
        self,
        jql: str,
        fields: list[str],
        expand: list[str] | None = None,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all issues matching query with automatic pagination."""
        start_at = 0
        collected: list[dict[str, Any]] = []

        while True:
            payload = self.get(
                "/rest/api/3/search",
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": batch_size,
                    "fields": ",".join(fields),
                    "expand": ",".join(expand or []),
                },
            )
            issues = payload.get("issues", [])
            collected.extend(issues)

            if start_at + len(issues) >= payload.get("total", 0):
                break
            start_at += len(issues)

        return collected

    def get_issue(self, issue_key: str, fields: list[str]) -> dict[str, Any]:
        return self.get(
            f"/rest/api/3/issue/{issue_key}",
            params={"fields": ",".join(fields), "expand": "renderedFields"},
        )
