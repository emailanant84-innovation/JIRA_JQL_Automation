from __future__ import annotations

from collections import deque
from typing import Any

from .jira_client import JiraApiClient

CORE_FIELDS = [
    "summary",
    "description",
    "issuetype",
    "status",
    "priority",
    "project",
    "parent",
    "labels",
    "assignee",
    "reporter",
    "creator",
    "created",
    "updated",
    "duedate",
    "resolution",
    "resolutiondate",
    "issuelinks",
    "subtasks",
    "fixVersions",
    "components",
]


class JiraProjectExtractor:
    """Extract all issues in a project plus linked issues and hierarchy."""

    def __init__(self, client: JiraApiClient) -> None:
        self.client = client

    def extract_project_graph(self, project_key: str) -> list[dict[str, Any]]:
        base_jql = f'project = "{project_key}" ORDER BY created ASC'
        seed_issues = self.client.search_issues(
            jql=base_jql,
            fields=CORE_FIELDS,
            expand=["names", "schema"],
        )

        by_key: dict[str, dict[str, Any]] = {issue["key"]: issue for issue in seed_issues}
        queue = deque(by_key.keys())

        while queue:
            key = queue.popleft()
            issue = by_key[key]
            fields = issue.get("fields", {})
            for link in fields.get("issuelinks", []):
                linked_issue = link.get("inwardIssue") or link.get("outwardIssue")
                if not linked_issue:
                    continue
                linked_key = linked_issue["key"]
                if linked_key in by_key:
                    continue
                full_issue = self.client.get_issue(linked_key, CORE_FIELDS)
                by_key[linked_key] = full_issue
                queue.append(linked_key)

        return list(by_key.values())
