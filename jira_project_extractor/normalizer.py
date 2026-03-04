from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .extractor import ExtractedIssueBundles
from .logging_utils import get_logger

logger = get_logger("normalizer")


@dataclass
class NormalizedJiraData:
    primary_issues: pd.DataFrame
    child_issues: pd.DataFrame
    subtask_issues: pd.DataFrame
    linked_scope_issues: pd.DataFrame
    issues: pd.DataFrame
    hierarchy: pd.DataFrame
    links: pd.DataFrame
    labels: pd.DataFrame
    components: pd.DataFrame
    fix_versions: pd.DataFrame


class JiraDataNormalizer:
    """Convert nested JIRA issue JSON into relational/normalized dataframes."""

    @staticmethod
    def _name(field_obj: dict[str, Any] | None) -> str | None:
        if not field_obj:
            return None
        return field_obj.get("displayName") or field_obj.get("name")

    @staticmethod
    def _stringify_custom_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for k in ["value", "name", "displayName", "text"]:
                if value.get(k) is not None:
                    return str(value.get(k))
            return str(value)
        if isinstance(value, list):
            flattened = [JiraDataNormalizer._stringify_custom_value(v) for v in value]
            return ", ".join([v for v in flattened if v])
        return str(value)

    @staticmethod
    def _get_named_custom_field(issue: dict[str, Any], aliases: list[str]) -> str | None:
        fields = issue.get("fields", {})
        names = issue.get("names", {})
        alias_set = {name.strip().lower() for name in aliases}

        for field_key, friendly_name in names.items():
            if not isinstance(friendly_name, str):
                continue
            if friendly_name.strip().lower() in alias_set:
                return JiraDataNormalizer._stringify_custom_value(fields.get(field_key))
        return None

    @staticmethod
    def _issue_row(issue: dict[str, Any]) -> dict[str, Any]:
        fields = issue.get("fields", {})
        labels = fields.get("labels", [])
        return {
            "issue_id": issue.get("id"),
            "issue_key": issue.get("key"),
            "parent_key": ((fields.get("parent") or {}).get("key")),
            "project_key": ((fields.get("project") or {}).get("key")),
            "issue_type": ((fields.get("issuetype") or {}).get("name")),
            "summary": fields.get("summary"),
            "description": fields.get("description"),
            "labels": ", ".join(labels) if labels else None,
            "status": ((fields.get("status") or {}).get("name")),
            "priority": ((fields.get("priority") or {}).get("name")),
            "assignee": JiraDataNormalizer._name(fields.get("assignee")),
            "reporter": JiraDataNormalizer._name(fields.get("reporter")),
            "creator": JiraDataNormalizer._name(fields.get("creator")),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "due_date": fields.get("duedate"),
            "resolution": ((fields.get("resolution") or {}).get("name")),
            "resolution_date": fields.get("resolutiondate"),
        }

    @staticmethod
    def _level_df(issues: list[dict[str, Any]], level_name: str) -> pd.DataFrame:
        rows = []
        for issue in issues:
            row = JiraDataNormalizer._issue_row(issue)
            row["level"] = level_name

            if level_name == "subtask":
                row["scope"] = JiraDataNormalizer._get_named_custom_field(issue, ["Scope"])
                row["test_criteria"] = JiraDataNormalizer._get_named_custom_field(
                    issue,
                    ["Test Criteria", "Acceptance Criteria"],
                )
                row["testing_results"] = JiraDataNormalizer._get_named_custom_field(
                    issue,
                    ["Testing Results", "Test Results"],
                )

            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        if level_name == "primary":
            return df.sort_values(by=["created", "issue_key"], kind="stable", na_position="last").reset_index(drop=True)

        return (
            df.sort_values(
                by=["parent_key", "created", "issue_key"],
                kind="stable",
                na_position="last",
            )
            .reset_index(drop=True)
        )

    @staticmethod
    def normalize(extracted: ExtractedIssueBundles) -> NormalizedJiraData:
        try:
            all_issues = extracted.all_issues()
            issue_rows: list[dict[str, Any]] = []
            hierarchy_rows: list[dict[str, Any]] = []
            link_rows: list[dict[str, Any]] = []
            label_rows: list[dict[str, Any]] = []
            component_rows: list[dict[str, Any]] = []
            version_rows: list[dict[str, Any]] = []

            for issue in all_issues:
                fields = issue.get("fields", {})
                issue_key = issue.get("key")
                issue_type = (fields.get("issuetype") or {}).get("name")

                issue_rows.append(JiraDataNormalizer._issue_row(issue))

                parent = fields.get("parent")
                if parent:
                    hierarchy_rows.append(
                        {
                            "parent_key": parent.get("key"),
                            "child_key": issue_key,
                            "relation": "parent-child",
                            "child_type": issue_type,
                        }
                    )

                for subtask in fields.get("subtasks", []):
                    hierarchy_rows.append(
                        {
                            "parent_key": issue_key,
                            "child_key": subtask.get("key"),
                            "relation": "parent-subtask",
                            "child_type": ((subtask.get("fields", {}).get("issuetype") or {}).get("name")),
                        }
                    )

                for link in fields.get("issuelinks", []):
                    link_type = link.get("type", {})
                    inward_issue = link.get("inwardIssue")
                    outward_issue = link.get("outwardIssue")

                    if inward_issue:
                        link_rows.append(
                            {
                                "from_issue": inward_issue.get("key"),
                                "to_issue": issue_key,
                                "direction": "inward",
                                "link_name": link_type.get("name"),
                                "relation_label": link_type.get("inward"),
                            }
                        )
                    if outward_issue:
                        link_rows.append(
                            {
                                "from_issue": issue_key,
                                "to_issue": outward_issue.get("key"),
                                "direction": "outward",
                                "link_name": link_type.get("name"),
                                "relation_label": link_type.get("outward"),
                            }
                        )

                for label in fields.get("labels", []):
                    label_rows.append({"issue_key": issue_key, "label": label})

                for component in fields.get("components", []):
                    component_rows.append(
                        {
                            "issue_key": issue_key,
                            "component_id": component.get("id"),
                            "component_name": component.get("name"),
                        }
                    )

                for version in fields.get("fixVersions", []):
                    version_rows.append(
                        {
                            "issue_key": issue_key,
                            "version_id": version.get("id"),
                            "version_name": version.get("name"),
                            "is_released": version.get("released"),
                        }
                    )

            out = NormalizedJiraData(
                primary_issues=JiraDataNormalizer._level_df(extracted.primary_issues, "primary"),
                child_issues=JiraDataNormalizer._level_df(extracted.child_issues, "child"),
                subtask_issues=JiraDataNormalizer._level_df(extracted.subtask_issues, "subtask"),
                linked_scope_issues=JiraDataNormalizer._level_df(extracted.linked_issues, "linked"),
                issues=pd.DataFrame(issue_rows),
                hierarchy=pd.DataFrame(hierarchy_rows),
                links=pd.DataFrame(link_rows),
                labels=pd.DataFrame(label_rows),
                components=pd.DataFrame(component_rows),
                fix_versions=pd.DataFrame(version_rows),
            )
            logger.info(
                "Normalization complete: primary=%s child=%s subtask=%s linked=%s",
                len(out.primary_issues),
                len(out.child_issues),
                len(out.subtask_issues),
                len(out.linked_scope_issues),
            )
            return out
        except Exception:
            logger.exception("Failed while normalizing JIRA issues")
            raise
