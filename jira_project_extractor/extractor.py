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
    "customfield_12947",  # tester
    "customfield_14646",  # target completion date
    "customfield_14852",  # desired start date
]

# Dedicated subtask field set: base core fields + required custom fields.
SUBTASK_EXTRA_FIELDS = [
    "customfield_11641",  # type of work
    "customfield_12884",  # scope
    "customfield_10010",  # test criteria
    "customfield_35544",  # testing results
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

    def all_issues(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for block in [self.primary_issues, self.child_issues, self.subtask_issues, self.linked_issues]:
            for issue in block:
                by_key[issue["key"]] = issue
        return list(by_key.values())


class JiraProjectExtractor:
    """Extract scope-limited issues: primary type -> children -> subtasks -> linked only."""

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
        try:
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
        except Exception:
            logger.exception("Failed while searching issues by key blocks")
            raise

    def build_primary_jql(self, project_key: str, query_filters: ProjectQueryFilters) -> str:
        try:
            project = project_key.replace('"', '\\"')
            issue_type = query_filters.issue_type.replace('"', '\\"')

            component_clause = ""
            if query_filters.components:
                component_list = self._quote_values(query_filters.components)
                component_clause = f"AND component in ({component_list}) "

            jql = (
                f'project = "{project}" '
                f'AND issuetype = "{issue_type}" '
                f"{component_clause}"
                f'AND created >= "{query_filters.created_start_date}" '
                f'AND created <= "{query_filters.created_end_date}" '
                f'AND resolutiondate >= "{query_filters.resolution_start_date}" '
                f'AND resolutiondate <= "{query_filters.resolution_end_date}" '
                "ORDER BY created ASC"
            )
            logger.info("Built primary JQL for project=%s issue_type=%s", project_key, query_filters.issue_type)
            return jql
        except Exception:
            logger.exception("Failed to build primary JQL")
            raise

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
        """Fetch children and preserve explicit parent->child mapping for each source key."""
        try:
            if not parent_keys:
                return []

            project = project_key.replace('"', '\\"')
            dedup: dict[str, dict[str, Any]] = {}
            explicit_map: dict[str, str] = {}

            for parent_key in parent_keys:
                parent_children = self._query_children_by_parent_key(project, parent_key, fields)
                for issue in parent_children:
                    key = issue["key"]
                    dedup[key] = issue
                    explicit_map[key] = parent_key

                epic_children: list[dict[str, Any]] = []
                try:
                    epic_children = self._query_children_by_epic_key(project, parent_key, fields)
                except Exception:
                    logger.warning("Epic Link query by label failed for %s; trying field-id fallback", parent_key)
                    if self.client.epic_link_field_id:
                        try:
                            epic_children = self._query_children_by_epic_field_id(
                                project,
                                parent_key,
                                self.client.epic_link_field_id,
                                fields,
                            )
                        except Exception:
                            logger.warning("Epic field-id query failed for %s", parent_key)

                for issue in epic_children:
                    key = issue["key"]
                    dedup[key] = issue
                    explicit_map[key] = parent_key

            for issue_key, parent_key in explicit_map.items():
                issue = dedup.get(issue_key)
                if not issue:
                    continue
                issue["__derived_parent_key"] = parent_key

            return list(dedup.values())
        except Exception:
            logger.exception("Failed extracting children for project=%s", project_key)
            raise

    @staticmethod
    def _linked_keys(seed_issues: list[dict[str, Any]], exclude: set[str]) -> list[str]:
        linked: set[str] = set()
        for issue in seed_issues:
            for link in issue.get("fields", {}).get("issuelinks", []):
                target = link.get("inwardIssue") or link.get("outwardIssue")
                if not target:
                    continue
                key = target.get("key")
                if key and key not in exclude:
                    linked.add(key)
        return sorted(linked)

    def extract_project_graph(
        self,
        project_key: str,
        query_filters: ProjectQueryFilters,
    ) -> ExtractedIssueBundles:
        try:
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
            anchor = [*primary_issues, *child_issues, *subtask_issues]
            linked_keys = self._linked_keys(anchor, exclude=in_scope_keys)
            linked_issues = self._search_by_keys(linked_keys, fields=CORE_FIELDS)

            logger.info(
                "Extraction complete: primary=%s child=%s subtask=%s linked=%s",
                len(primary_issues),
                len(child_issues),
                len(subtask_issues),
                len(linked_issues),
            )
            return ExtractedIssueBundles(
                primary_issues=primary_issues,
                child_issues=child_issues,
                subtask_issues=subtask_issues,
                linked_issues=linked_issues,
            )
        except Exception:
            logger.exception("Failed extracting scoped hierarchy for project %s", project_key)
            raise
