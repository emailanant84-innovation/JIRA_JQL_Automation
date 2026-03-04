from __future__ import annotations

from collections import deque
from dataclasses import dataclass
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
    "customfield_*",
]


@dataclass(slots=True)
class ProjectQueryFilters:
    components: list[str]
    created_on_or_after: str
    desired_start_on_or_after: str


class JiraProjectExtractor:
    """Extract all issues in a project plus linked issues and hierarchy."""

    def __init__(self, client: JiraApiClient, desired_start_field: str = '"Start date"') -> None:
        self.client = client
        self.desired_start_field = desired_start_field

    @staticmethod
    def _quote_values(values: list[str]) -> str:
        escaped = [value.replace('"', '\\"') for value in values]
        return ", ".join(f'"{value}"' for value in escaped)

    def build_project_jql(self, project_key: str, query_filters: ProjectQueryFilters) -> str:
        project = project_key.replace('"', '\\"')
        component_list = self._quote_values(query_filters.components)

        return (
            f'project = "{project}" '
            f'AND component in ({component_list}) '
            f'AND created >= "{query_filters.created_on_or_after}" '
            f'AND {self.desired_start_field} >= "{query_filters.desired_start_on_or_after}" '
            "ORDER BY created ASC"
        )

    def extract_project_graph(
        self,
        project_key: str,
        query_filters: ProjectQueryFilters,
    ) -> list[dict[str, Any]]:
        base_jql = self.build_project_jql(project_key, query_filters)
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
