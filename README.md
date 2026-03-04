# JIRA Project Intelligent Extractor

A modular Python application that:
- Uses JIRA username/password login via the local OS username (from `USERNAME` / `USER`) and password entered in the GUI.
- Connects to a fixed JIRA URL: `https://wim-jira.wellsfargo.com`.
- Uses TLS verification certificate path: `~/Downloads/WellsFargoVerification.cer`.
- Runs expert-level JQL extraction using **mandatory filters**: `project`, `components`, `created >=`, and `"Start date" >=`.
- Extracts all matching project issues and traverses linked issues recursively.
- Normalizes issue, hierarchy, links, labels, components, and versions into clean pandas DataFrames.
- Cleans text noise (line/page breaks, excessive whitespace), deduplicates rows, and exports CSV tables.
- Saves output automatically to `~/Downloads/jira_project_extractor_output`.
- Logs process events, issue-level failures, and exceptions from modules into `~/Downloads/jira_project_extractor_output/jira_project_extractor.log`.
- Provides a Tkinter GUI for running extraction and interactive filtering by **multiple issue keys** entered as comma-separated values.

## Modules

- `jira_project_extractor/config.py`: fixed connection settings + downloads path helpers.
- `jira_project_extractor/logging_utils.py`: centralized logger setup and file handler.
- `jira_project_extractor/jira_client.py`: JIRA Python SDK client and pagination.
- `jira_project_extractor/extractor.py`: JQL builder + project and linked issue graph extraction.
- `jira_project_extractor/normalizer.py`: nested JSON → normalized DataFrames.
- `jira_project_extractor/cleaner.py`: text cleaning and deduplication.
- `jira_project_extractor/orchestrator.py`: end-to-end pipeline orchestration + CSV persistence.
- `jira_project_extractor/gui.py`: GUI orchestration and table filtering.
- `main.py`: app entrypoint.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## GUI Inputs (Mandatory)

- Project Key
- JIRA Password
- Components (comma-separated)
- Creation Date (YYYY-MM-DD)
- Desired Start Date (YYYY-MM-DD)

## Table Filter

- Issue Key Filter supports multiple keys separated by comma (for example: `ABC-123, ABC-456, XYZ-9`).
