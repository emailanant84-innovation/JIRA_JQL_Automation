from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .jira_client import JiraApiClient
from .logging_utils import get_logger

logger = get_logger("extractor")

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
    "customfield_12947",
    "customfield_14646",
    "customfield_14852",
]

SUBTASK_EXTRA_FIELDS = [
    "customfield_11641",
    "customfield_12884",
    "customfield_10010",
    "customfield_35544",
]
SUBTASK_CORE_FIELDS = [*CORE_FIELDS, *SUBTASK_EXTRA_FIELDS]


@dataclass(slots=True)
class ProjectQueryFilters:
    components: list[str]
    created_start_date: str
    created_end_date: str
    resolution_start_date: str
    resolution_end_date: str
    issue_type: str


@dataclass(slots=True)
class ExtractedIssueBundles:
    primary_issues: list[dict[str, Any]]
    child_issues: list[dict[str, Any]]
    subtask_issues: list[dict[str, Any]]
    linked_issues: list[dict[str, Any]]


class JiraProjectExtractor:
    def __init__(self, client: JiraApiClient) -> None:
        self.client = client

    @staticmethod
    def _quote_values(values: list[str]) -> str:
        escaped = [value.replace('"', '\\"') for value in values]
        return ", ".join(f'"{value}"' for value in escaped)

    @staticmethod
    def _chunk(values: list[str], size: int = 100) -> list[list[str]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    def _search_by_keys(self, issue_keys: list[str], fields: list[str] | None = None) -> list[dict[str, Any]]:
        if not issue_keys:
            return []
        collected: list[dict[str, Any]] = []
        for block in self._chunk(issue_keys, size=100):
            key_values = self._quote_values(block)
            jql = f"issuekey in ({key_values}) ORDER BY created ASC"
            collected.extend(
                self.client.search_issues(
                    jql=jql,
                    fields=fields or CORE_FIELDS,
                    expand=["names", "schema", "renderedFields"],
                )
            )
        return collected

    def build_primary_jql(self, project_key: str, query_filters: ProjectQueryFilters) -> str:
        project = project_key.replace('"', '\\"')
        issue_type = query_filters.issue_type.replace('"', '\\"')

        parts = [
            f'project = "{project}"',
            f'issuetype = "{issue_type}"',
            f'created >= "{query_filters.created_start_date}"',
            f'created <= "{query_filters.created_end_date}"',
        ]

        if query_filters.components:
            parts.append(f"component in ({self._quote_values(query_filters.components)})")

        if query_filters.resolution_start_date:
            parts.append(f'resolutiondate >= "{query_filters.resolution_start_date}"')
        if query_filters.resolution_end_date:
            parts.append(f'resolutiondate <= "{query_filters.resolution_end_date}"')

        return " AND ".join(parts) + " ORDER BY created ASC"

    def _query_children_by_parent_key(self, project: str, parent_key: str, fields: list[str]) -> list[dict[str, Any]]:
        jql = f'project = "{project}" AND parent = "{parent_key}" ORDER BY created ASC, key ASC'
        return self.client.search_issues(jql=jql, fields=fields, expand=["names", "schema", "renderedFields"])

    def _query_children_by_epic_key(self, project: str, parent_key: str, fields: list[str]) -> list[dict[str, Any]]:
        jql = f'project = "{project}" AND "Epic Link" = "{parent_key}" ORDER BY created ASC, key ASC'
        return self.client.search_issues(jql=jql, fields=fields, expand=["names", "schema", "renderedFields"])

    def _query_children_by_epic_field_id(self, project: str, parent_key: str, epic_field_id: str, fields: list[str]) -> list[dict[str, Any]]:
        jql = f'project = "{project}" AND {epic_field_id} = "{parent_key}" ORDER BY created ASC, key ASC'
        return self.client.search_issues(jql=jql, fields=fields, expand=["names", "schema", "renderedFields"])

    def _extract_children(self, project_key: str, parent_keys: list[str], fields: list[str]) -> list[dict[str, Any]]:
        if not parent_keys:
            return []

        project = project_key.replace('"', '\\"')
        dedup: dict[str, dict[str, Any]] = {}
        explicit_map: dict[str, str] = {}

        for parent_key in parent_keys:
            for issue in self._query_children_by_parent_key(project, parent_key, fields):
                dedup[issue["key"]] = issue
                explicit_map[issue["key"]] = parent_key

            epic_children: list[dict[str, Any]] = []
            try:
                epic_children = self._query_children_by_epic_key(project, parent_key, fields)
            except Exception:
                if self.client.epic_link_field_id:
                    try:
                        epic_children = self._query_children_by_epic_field_id(project, parent_key, self.client.epic_link_field_id, fields)
                    except Exception:
                        logger.warning("Epic field-id query failed for %s", parent_key)

            for issue in epic_children:
                dedup[issue["key"]] = issue
                explicit_map[issue["key"]] = parent_key

        for issue_key, parent_key in explicit_map.items():
            if issue_key in dedup:
                dedup[issue_key]["__derived_parent_key"] = parent_key

        return list(dedup.values())

    @staticmethod
    def _linked_keys(seed_issues: list[dict[str, Any]], exclude: set[str]) -> list[str]:
        linked: set[str] = set()
        for issue in seed_issues:
            for link in issue.get("fields", {}).get("issuelinks", []):
                target = link.get("inwardIssue") or link.get("outwardIssue")
                if target and target.get("key") and target["key"] not in exclude:
                    linked.add(target["key"])
        return sorted(linked)

    def extract_project_graph(self, project_key: str, query_filters: ProjectQueryFilters) -> ExtractedIssueBundles:
        primary_jql = self.build_primary_jql(project_key, query_filters)
        primary_issues = self.client.search_issues(
            jql=primary_jql,
            fields=CORE_FIELDS,
            expand=["names", "schema", "renderedFields"],
        )

        primary_keys = [issue["key"] for issue in primary_issues]
        child_issues = self._extract_children(project_key, primary_keys, CORE_FIELDS)
        child_keys = [issue["key"] for issue in child_issues]
        subtask_issues = self._extract_children(project_key, child_keys, SUBTASK_CORE_FIELDS)

        in_scope_keys = set(primary_keys) | set(child_keys) | {issue["key"] for issue in subtask_issues}
        linked_keys = self._linked_keys(subtask_issues, exclude=in_scope_keys)
        linked_issues = self._search_by_keys(linked_keys, fields=CORE_FIELDS)

        return ExtractedIssueBundles(
            primary_issues=primary_issues,
            child_issues=child_issues,
            subtask_issues=subtask_issues,
            linked_issues=linked_issues,
        )
