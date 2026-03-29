# JIRA Project Intelligent Extractor

A modular Python application that:
- Uses JIRA username/password login via the local OS username (from `USERNAME` / `USER`) and password entered in the GUI.
- Connects to a fixed JIRA URL: `https://wim-jira.wellsfargo.com`.
- Uses TLS verification certificate path: `~/Downloads/WellsFargoVerification.cer`.
- Applies mandatory JQL filters first to reduce extraction load: `project`, `issuetype`, `created between <start/end>`, and `resolutiondate between <start/end>`. Components filter is optional.
- Uses JQL sorting compatible with restricted JIRA instances (avoids `ORDER BY parent`), and then orders child/subtask tables by parent locally.
- Extracts a **limited hierarchy only**: selected issue type (primary level) → direct child issues (via `parent` and `"Epic Link"`) → child subtasks.
- Extracts one additional linked-issues list for issues linked to **subtasks only** (from `subtask_issues`), without traversing deeper.
- Produces ordered level-wise tables only: `primary_issues`, `child_issues`, `subtask_issues`, `linked_issues`.
- `linked_issues` includes `linked_to_subtask_keys` showing which subtask issue key(s) each linked issue came from.
- Includes `labels` in primary issue rows and includes `labels`, `scope`, `test_criteria`, and `testing_results` in subtask rows when those fields exist.
- Uses a dedicated subtask core-field set that explicitly includes custom fields required in subtask outputs:
  - `customfield_11641` as `type_of_work`
  - `customfield_12884` as `scope`
  - `customfield_10010` as `test_criteria`
  - `customfield_35544` as `testing_results`
- Adds primary-issue custom fields to primary table/CSV:
  - `customfield_12947` as `tester`
  - `customfield_14646` as `target_completion_date`
  - `customfield_14852` as `desired_start_date`
- Preserves explicit Epic→Task mapping during child expansion (per-Epic queries) and writes that mapped Epic key into `parent_key` for child rows/CSV.
- Cleans text noise (line/page breaks, excessive whitespace), deduplicates rows, and exports CSV tables.
- Saves output automatically to `~/Downloads/jira_project_extractor_output`.
- Logs process events, issue-level failures, and exceptions from modules into `~/Downloads/jira_project_extractor_output/jira_project_extractor.log`.
- Provides a Tkinter GUI for running extraction and interactive filtering by **multiple issue keys** entered as comma-separated values.

## Modules

- `jira_project_extractor/config.py`: fixed connection settings + downloads path helpers.
- `jira_project_extractor/logging_utils.py`: centralized logger setup and file handler.
- `jira_project_extractor/jira_client.py`: JIRA Python SDK client and pagination.
- `jira_project_extractor/extractor.py`: scoped JQL builder + primary/child/subtask/linked extraction strategy.
- `jira_project_extractor/normalizer.py`: nested JSON → level-wise DataFrames.
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
- Issue Type (for example: `Epic`, `Feature`, `Task`)
- Components (comma-separated, optional)
- Creation Date Start (YYYY-MM-DD)
- Creation Date End (YYYY-MM-DD)
- Resolution Date Start (YYYY-MM-DD, optional)
- Resolution Date End (YYYY-MM-DD, optional)

## Table Filter

- Issue Key Filter supports multiple keys separated by comma (for example: `ABC-123, ABC-456, XYZ-9`).
