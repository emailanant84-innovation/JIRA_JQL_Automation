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
    linked_issues: pd.DataFrame


class JiraDataNormalizer:
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
            for key in ["value", "name", "displayName", "text", "key"]:
                if value.get(key) is not None:
                    return str(value.get(key))
            return str(value)
        if isinstance(value, list):
            flattened = [JiraDataNormalizer._stringify_custom_value(item) for item in value]
            return ", ".join([item for item in flattened if item])
        return str(value)

    @staticmethod
    def _custom_field(issue: dict[str, Any], field_id: str) -> str | None:
        fields = issue.get("fields", {})
        rendered = issue.get("renderedFields", {})
        if isinstance(fields, dict) and fields.get(field_id) is not None:
            return JiraDataNormalizer._stringify_custom_value(fields.get(field_id))
        if isinstance(rendered, dict) and rendered.get(field_id) is not None:
            return JiraDataNormalizer._stringify_custom_value(rendered.get(field_id))
        return None

    @staticmethod
    def _issue_row(issue: dict[str, Any]) -> dict[str, Any]:
        fields = issue.get("fields", {})
        labels = fields.get("labels", [])
        parent_key = ((fields.get("parent") or {}).get("key")) or issue.get("__derived_parent_key")

        return {
            "issue_id": issue.get("id"),
            "issue_key": issue.get("key"),
            "parent_key": parent_key,
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
                row["type_of_work"] = JiraDataNormalizer._custom_field(issue, "customfield_11641")
                row["scope"] = JiraDataNormalizer._custom_field(issue, "customfield_12884")
                row["test_criteria"] = JiraDataNormalizer._custom_field(issue, "customfield_10010")
                row["testing_results"] = JiraDataNormalizer._custom_field(issue, "customfield_35544")

            if level_name == "primary":
                row["tester"] = JiraDataNormalizer._custom_field(issue, "customfield_12947")
                row["target_completion_date"] = JiraDataNormalizer._custom_field(issue, "customfield_14646")
                row["desired_start_date"] = JiraDataNormalizer._custom_field(issue, "customfield_14852")

            if level_name == "linked":
                row["linked_to_subtask_keys"] = issue.get("__linked_subtask_keys")

            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        if level_name == "primary":
            return df.sort_values(by=["created", "issue_key"], kind="stable", na_position="last").reset_index(drop=True)

        return df.sort_values(by=["parent_key", "created", "issue_key"], kind="stable", na_position="last").reset_index(drop=True)

    @staticmethod
    def normalize(extracted: ExtractedIssueBundles) -> NormalizedJiraData:
        try:
            out = NormalizedJiraData(
                primary_issues=JiraDataNormalizer._level_df(extracted.primary_issues, "primary"),
                child_issues=JiraDataNormalizer._level_df(extracted.child_issues, "child"),
                subtask_issues=JiraDataNormalizer._level_df(extracted.subtask_issues, "subtask"),
                linked_issues=JiraDataNormalizer._level_df(extracted.linked_issues, "linked"),
            )
            logger.info(
                "Normalization complete: primary=%s child=%s subtask=%s linked=%s",
                len(out.primary_issues),
                len(out.child_issues),
                len(out.subtask_issues),
                len(out.linked_issues),
            )
            return out
        except Exception:
            logger.exception("Failed while normalizing JIRA issues")
            raise
