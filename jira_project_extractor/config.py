from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .logging_utils import get_logger

logger = get_logger("config")


@dataclass(slots=True)
class JiraConfig:
    """Connection settings for JIRA authentication used in this environment."""

    password: str
    username: str | None = None
    base_url: str = "https://wim-jira.wellsfargo.com"
    verify_cert_path: str | None = None

    def resolved_username(self) -> str:
        try:
            user = self.username or os.environ.get("USERNAME") or os.environ.get("USER")
            if not user:
                raise ValueError("Unable to resolve username from environment (USERNAME/USER).")
            return user
        except Exception as exc:
            logger.exception("Failed to resolve username")
            raise

    def resolved_verify_cert_path(self) -> str:
        try:
            if self.verify_cert_path:
                return self.verify_cert_path
            return str(Path.home() / "Downloads" / "WellsFargoVerification.cer")
        except Exception:
            logger.exception("Failed to resolve verification certificate path")
            raise

    def downloads_output_dir(self) -> Path:
        try:
            path = Path.home() / "Downloads" / "jira_project_extractor_output"
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            logger.exception("Failed to prepare downloads output directory")
            raise
