from __future__ import annotations

import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _default_log_path() -> Path:
    return Path.home() / "Downloads" / "jira_project_extractor_output" / "jira_project_extractor.log"


def configure_logging(log_file: str | Path | None = None) -> Path:
    target = Path(log_file) if log_file else _default_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("jira_project_extractor")
    root_logger.setLevel(logging.INFO)

    existing = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    if existing:
        return target

    file_handler = logging.FileHandler(target, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_logger.addHandler(file_handler)

    return target


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"jira_project_extractor.{name}")
