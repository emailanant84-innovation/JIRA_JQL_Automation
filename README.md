# JIRA Project Intelligent Extractor

A modular Python application that:
- Uses JIRA username/password login via the local OS username (from `USERNAME` / `USER`) and password entered in the GUI.
- Connects to a fixed JIRA URL: `https://wim-jira.wellsfargo.com`.
- Uses TLS verification certificate path: `~/Downloads/WellsFargoVerification.cer`.
- Extracts all issues from a project and traverses linked issues recursively.
- Normalizes issue, hierarchy, links, labels, components, and versions into clean pandas DataFrames.
- Cleans text noise (line/page breaks, excessive whitespace), deduplicates rows, and exports CSV tables.
- Saves output automatically to `~/Downloads/jira_project_extractor_output`.
- Provides a Tkinter GUI for running extraction and interactive filtering by issue key/type.

## Modules

- `jira_project_extractor/config.py`: fixed connection settings + downloads path helpers.
- `jira_project_extractor/jira_client.py`: JIRA Python SDK client and pagination.
- `jira_project_extractor/extractor.py`: project + linked issue graph extraction.
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

## GUI Inputs

- Project Key
- JIRA Password

No email/API token input is required.
