# JIRA Project Intelligent Extractor

A modular Python application that:
- Connects to JIRA using URL + email + API token.
- Extracts all issues from a project.
- Traverses linked issues recursively to build a broader issue graph.
- Normalizes issue, hierarchy, links, labels, components, and versions into clean pandas DataFrames.
- Cleans text noise (line/page breaks, excessive whitespace), deduplicates rows, and exports CSV tables.
- Provides a Tkinter GUI for running extraction and interactive filtering by issue key/type.

## Modules

- `jira_project_extractor/config.py`: connection config.
- `jira_project_extractor/jira_client.py`: JIRA REST API client with pagination.
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

## Notes

- Works with JIRA Cloud REST API v3 endpoints.
- The app captures both explicit hierarchy (`parent`, `subtasks`) and linked issue relations (`issuelinks`) to support diverse structures such as Epic → Story → Subtask, or Feature → Milestone → Task chains.
