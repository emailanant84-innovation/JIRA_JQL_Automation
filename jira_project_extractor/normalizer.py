from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .logging_utils import get_logger

logger = get_logger("normalizer")


@dataclass
class NormalizedJiraData:
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
    def normalize(issues: list[dict[str, Any]]) -> NormalizedJiraData:
        try:
            issue_rows: list[dict[str, Any]] = []
            hierarchy_rows: list[dict[str, Any]] = []
            link_rows: list[dict[str, Any]] = []
            label_rows: list[dict[str, Any]] = []
            component_rows: list[dict[str, Any]] = []
            version_rows: list[dict[str, Any]] = []

            for issue in issues:
                fields = issue.get("fields", {})
                issue_key = issue.get("key")
                issue_type = (fields.get("issuetype") or {}).get("name")

                issue_rows.append(
                    {
                        "issue_id": issue.get("id"),
                        "issue_key": issue_key,
                        "project_key": ((fields.get("project") or {}).get("key")),
                        "issue_type": issue_type,
                        "summary": fields.get("summary"),
                        "description": fields.get("description"),
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
                )

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
                issues=pd.DataFrame(issue_rows),
                hierarchy=pd.DataFrame(hierarchy_rows),
                links=pd.DataFrame(link_rows),
                labels=pd.DataFrame(label_rows),
                components=pd.DataFrame(component_rows),
                fix_versions=pd.DataFrame(version_rows),
            )
            logger.info("Normalization complete for %s issues", len(issue_rows))
            return out
        except Exception:
            logger.exception("Failed while normalizing JIRA issues")
            raise
