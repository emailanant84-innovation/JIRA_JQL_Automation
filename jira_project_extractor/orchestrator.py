from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .attachment_extractor import JiraAttachmentExtractor
from .cleaner import DataCleaner
from .config import JiraConfig
from .extractor import JiraProjectExtractor, ProjectQueryFilters
from .jira_client import JiraApiClient
from .logging_utils import get_logger
from .normalizer import JiraDataNormalizer, NormalizedJiraData

logger = get_logger("orchestrator")


class JiraExtractionOrchestrator:
    """Coordinate extraction, normalization, cleaning and persistence."""

    def __init__(self, config: JiraConfig) -> None:
        try:
            self.config = config
            self.client = JiraApiClient(config)
            self.extractor = JiraProjectExtractor(self.client)
            self.attachment_extractor = JiraAttachmentExtractor(self.client)
        except Exception:
            logger.exception("Failed to initialize orchestrator")
            raise

    def run(self, project_key: str, query_filters: ProjectQueryFilters) -> NormalizedJiraData:
        try:
            raw_issues = self.extractor.extract_project_graph(project_key, query_filters)
            attachments_root = self.config.downloads_output_dir() / "attachments"
            self.attachment_extractor.extract_from_bundles(raw_issues, attachments_root)
            normalized = JiraDataNormalizer.normalize(raw_issues)

            cleaned = {
                name: DataCleaner.clean_dataframe(df)
                for name, df in asdict(normalized).items()
            }
            logger.info("Pipeline run completed for project %s", project_key)
            return NormalizedJiraData(**cleaned)
        except Exception:
            logger.exception("Pipeline run failed for project %s", project_key)
            raise

    def save_to_csv(self, data: NormalizedJiraData, out_dir: str | Path | None = None) -> Path:
        try:
            out_path = Path(out_dir) if out_dir else self.config.downloads_output_dir()
            out_path.mkdir(parents=True, exist_ok=True)

            for name, df in asdict(data).items():
                df.to_csv(out_path / f"{name}.csv", index=False)
            logger.info("Saved normalized CSV files to %s", out_path)
            return out_path
        except Exception:
            logger.exception("Failed to save CSV outputs")
            raise
