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
    "customfield_*",
]


@dataclass(slots=True)
class ProjectQueryFilters:
    components: list[str]
    created_on_or_after: str
    desired_start_on_or_after: str
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

    def __init__(self, client: JiraApiClient, desired_start_field: str = '"Start date"') -> None:
        self.client = client
        self.desired_start_field = desired_start_field

    @staticmethod
    def _quote_values(values: list[str]) -> str:
        escaped = [value.replace('"', '\\"') for value in values]
        return ", ".join(f'"{value}"' for value in escaped)

    @staticmethod
    def _chunk(values: list[str], size: int = 100) -> list[list[str]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    def _search_by_keys(self, issue_keys: list[str]) -> list[dict[str, Any]]:
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
                        fields=CORE_FIELDS,
                        expand=["names", "schema"],
                    )
                )
            return collected
        except Exception:
            logger.exception("Failed while searching issues by key blocks")
            raise

    def build_primary_jql(self, project_key: str, query_filters: ProjectQueryFilters) -> str:
        try:
            project = project_key.replace('"', '\\"')
            component_list = self._quote_values(query_filters.components)
            issue_type = query_filters.issue_type.replace('"', '\\"')

            jql = (
                f'project = "{project}" '
                f'AND issuetype = "{issue_type}" '
                f'AND component in ({component_list}) '
                f'AND created >= "{query_filters.created_on_or_after}" '
                f'AND {self.desired_start_field} >= "{query_filters.desired_start_on_or_after}" '
                "ORDER BY created ASC"
            )
            logger.info("Built primary JQL for project=%s issue_type=%s", project_key, query_filters.issue_type)
            return jql
        except Exception:
            logger.exception("Failed to build primary JQL")
            raise

    def _query_children_parent_or_epic(self, project: str, keys: str) -> list[dict[str, Any]]:
        jql = (
            f'project = "{project}" AND '
            f'((parent in ({keys})) OR ("Epic Link" in ({keys}))) '
            "ORDER BY created ASC, key ASC"
        )
        return self.client.search_issues(jql=jql, fields=CORE_FIELDS, expand=["names", "schema"])

    def _query_children_parent_only(self, project: str, keys: str) -> list[dict[str, Any]]:
        jql = f'project = "{project}" AND (parent in ({keys})) ORDER BY created ASC, key ASC'
        return self.client.search_issues(jql=jql, fields=CORE_FIELDS, expand=["names", "schema"])

    def _query_children_epic_field(self, project: str, keys: str, epic_field_id: str) -> list[dict[str, Any]]:
        jql = f'project = "{project}" AND ({epic_field_id} in ({keys})) ORDER BY created ASC, key ASC'
        return self.client.search_issues(jql=jql, fields=CORE_FIELDS, expand=["names", "schema"])

    @staticmethod
    def _normalized_label(text: str) -> str:
        return "".join(ch for ch in text.lower() if ch.isalnum())

    @staticmethod
    def _issue_field_labels(issue: dict[str, Any]) -> dict[str, str]:
        labels: dict[str, str] = {}
        names = issue.get("names", {})
        if isinstance(names, dict):
            for field_id, label in names.items():
                if isinstance(field_id, str) and isinstance(label, str):
                    labels[field_id] = label
        catalog = issue.get("__field_catalog", {})
        if isinstance(catalog, dict):
            for field_id, label in catalog.items():
                if isinstance(field_id, str) and isinstance(label, str) and field_id not in labels:
                    labels[field_id] = label
        return labels

    @staticmethod
    def _derive_parent_key(issue: dict[str, Any], allowed_parents: set[str]) -> str | None:
        fields = issue.get("fields", {})
        parent_key = ((fields.get("parent") or {}).get("key"))
        if parent_key in allowed_parents:
            return parent_key

        epic_field_id = issue.get("__epic_link_field_id")
        if epic_field_id:
            epic_parent = fields.get(epic_field_id)
            if isinstance(epic_parent, str) and epic_parent in allowed_parents:
                return epic_parent

        # Fallback: detect likely Epic/Parent link fields via field label metadata.
        labels = JiraProjectExtractor._issue_field_labels(issue)
        link_aliases = {"epiclink", "parentlink", "featurelink"}
        for field_id, label in labels.items():
            if JiraProjectExtractor._normalized_label(label) not in link_aliases:
                continue
            candidate = fields.get(field_id)
            if isinstance(candidate, str) and candidate in allowed_parents:
                return candidate

        # Last fallback: any custom field carrying one of allowed parent keys.
        for field_id, value in fields.items():
            if not isinstance(field_id, str) or not field_id.startswith("customfield_"):
                continue
            if isinstance(value, str) and value in allowed_parents:
                return value
        return parent_key

    def _attach_derived_parent_keys(self, issues: list[dict[str, Any]], parent_keys: list[str]) -> list[dict[str, Any]]:
        allowed = set(parent_keys)
        for issue in issues:
            derived = self._derive_parent_key(issue, allowed)
            if derived:
                issue["__derived_parent_key"] = derived
        return issues

    def _extract_children(self, project_key: str, parent_keys: list[str]) -> list[dict[str, Any]]:
        """Fetch children via both parent and Epic Link semantics."""
        try:
            if not parent_keys:
                return []
            out: list[dict[str, Any]] = []
            project = project_key.replace('"', '\\"')

            for block in self._chunk(parent_keys, size=100):
                keys = self._quote_values(block)
                try:
                    out.extend(self._query_children_parent_or_epic(project, keys))
                except Exception:
                    logger.warning("Combined parent/Epic Link JQL failed; trying fallback queries")
                    out.extend(self._query_children_parent_only(project, keys))
                    if self.client.epic_link_field_id:
                        try:
                            out.extend(self._query_children_epic_field(project, keys, self.client.epic_link_field_id))
                        except Exception:
                            logger.warning("Epic field-id fallback query also failed")

            # Deduplicate + attach derived parent key for rows linked via Epic Link.
            by_key = {issue["key"]: issue for issue in out}
            deduped = list(by_key.values())
            return self._attach_derived_parent_keys(deduped, parent_keys)
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
                expand=["names", "schema"],
            )

            primary_keys = [issue["key"] for issue in primary_issues]
            child_issues = self._extract_children(project_key, primary_keys)
            child_keys = [issue["key"] for issue in child_issues]
            subtask_issues = self._extract_children(project_key, child_keys)

            in_scope_keys = set(primary_keys) | set(child_keys) | {issue["key"] for issue in subtask_issues}
            anchor = [*primary_issues, *child_issues, *subtask_issues]
            linked_keys = self._linked_keys(anchor, exclude=in_scope_keys)
            linked_issues = self._search_by_keys(linked_keys)

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
