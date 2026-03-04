from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class JiraConfig:
    """Connection settings for JIRA authentication used in this environment."""

    password: str
    username: str | None = None
    base_url: str = "https://wim-jira.wellsfargo.com"
    verify_cert_path: str | None = None

    def resolved_username(self) -> str:
        user = self.username or os.environ.get("USERNAME") or os.environ.get("USER")
        if not user:
            raise ValueError("Unable to resolve username from environment (USERNAME/USER).")
        return user

    def resolved_verify_cert_path(self) -> str:
        if self.verify_cert_path:
            return self.verify_cert_path
        return str(Path.home() / "Downloads" / "WellsFargoVerification.cer")

    def downloads_output_dir(self) -> Path:
        return Path.home() / "Downloads" / "jira_project_extractor_output"
