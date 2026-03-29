from __future__ import annotations

from pathlib import Path
from typing import Any

from .extractor import ExtractedIssueBundles
from .jira_client import JiraApiClient
from .logging_utils import get_logger

logger = get_logger("attachment_extractor")


class JiraAttachmentExtractor:
    """Download JIRA issue attachments into level-specific folders."""

    LEVEL_TO_BUNDLE_ATTR = {
        "primary": "primary_issues",
        "child": "child_issues",
        "subtask": "subtask_issues",
        "linked": "linked_issues",
    }

    def __init__(self, client: JiraApiClient) -> None:
        self.client = client

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = filename.replace("/", "_").replace("\\", "_").strip()
        return cleaned or "attachment.bin"

    @staticmethod
    def _unique_path(candidate: Path) -> Path:
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        parent = candidate.parent
        counter = 1

        while True:
            next_path = parent / f"{stem}_{counter}{suffix}"
            if not next_path.exists():
                return next_path
            counter += 1

    def _download_issue_attachments(self, issue: dict[str, Any], folder: Path) -> int:
        issue_id = str(issue.get("id") or issue.get("key") or "unknown")
        attachments = issue.get("fields", {}).get("attachment") or []
        downloaded_count = 0

        for attachment in attachments:
            content_url = attachment.get("content")
            attachment_name = attachment.get("filename")
            if not content_url or not attachment_name:
                continue

            target_name = f"{issue_id}_{self._safe_filename(attachment_name)}"
            destination = self._unique_path(folder / target_name)

            self.client.download_binary(content_url, destination)
            downloaded_count += 1

        return downloaded_count

    def extract_from_bundles(self, extracted: ExtractedIssueBundles, attachments_root: Path) -> None:
        attachments_root.mkdir(parents=True, exist_ok=True)

        for level_name, bundle_attr in self.LEVEL_TO_BUNDLE_ATTR.items():
            level_folder = attachments_root / level_name
            level_folder.mkdir(parents=True, exist_ok=True)

            issues = getattr(extracted, bundle_attr)
            level_downloaded = 0
            for issue in issues:
                level_downloaded += self._download_issue_attachments(issue, level_folder)

            logger.info(
                "Attachment extraction completed for %s issues: downloaded=%s",
                level_name,
                level_downloaded,
            )
