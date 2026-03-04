from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .cleaner import DataCleaner
from .config import JiraConfig
from .extractor import JiraProjectExtractor
from .jira_client import JiraApiClient
from .normalizer import JiraDataNormalizer, NormalizedJiraData


class JiraExtractionOrchestrator:
    """Coordinate extraction, normalization, cleaning and persistence."""

    def __init__(self, config: JiraConfig) -> None:
        self.config = config
        self.client = JiraApiClient(config)
        self.extractor = JiraProjectExtractor(self.client)

    def run(self, project_key: str) -> NormalizedJiraData:
        raw_issues = self.extractor.extract_project_graph(project_key)
        normalized = JiraDataNormalizer.normalize(raw_issues)

        cleaned = {
            name: DataCleaner.clean_dataframe(df)
            for name, df in asdict(normalized).items()
        }
        return NormalizedJiraData(**cleaned)

    def save_to_csv(self, data: NormalizedJiraData, out_dir: str | Path | None = None) -> Path:
        out_path = Path(out_dir) if out_dir else self.config.downloads_output_dir()
        out_path.mkdir(parents=True, exist_ok=True)

        for name, df in asdict(data).items():
            df.to_csv(out_path / f"{name}.csv", index=False)
        return out_path
