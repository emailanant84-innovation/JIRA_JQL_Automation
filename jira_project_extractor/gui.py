from __future__ import annotations

import tkinter as tk
from dataclasses import asdict
from tkinter import messagebox, ttk

import pandas as pd

from .config import JiraConfig
from .extractor import ProjectQueryFilters
from .logging_utils import get_logger
from .normalizer import NormalizedJiraData
from .orchestrator import JiraExtractionOrchestrator

logger = get_logger("gui")


class JiraExtractionGUI:
    """Tkinter GUI to orchestrate extraction and inspect normalized tables."""

    TABLES = ["issues", "hierarchy", "links", "labels", "components", "fix_versions"]

    def __init__(self) -> None:
        try:
            self.root = tk.Tk()
            self.root.title("JIRA Project Extractor")
            self.root.geometry("1280x820")

            self.results: NormalizedJiraData | None = None
            self.table_views: dict[str, ttk.Treeview] = {}
            self.base_tables: dict[str, pd.DataFrame] = {}

            self._build_form()
            self._build_tabs()
        except Exception:
            logger.exception("Failed to initialize GUI")
            raise

    def _build_form(self) -> None:
        try:
            form = ttk.Frame(self.root, padding=10)
            form.pack(fill="x")

            ttk.Label(form, text="JIRA URL (fixed)").grid(row=0, column=0, sticky="w", pady=3)
            ttk.Label(form, text="https://wim-jira.wellsfargo.com").grid(row=0, column=1, sticky="w", pady=3)

            ttk.Label(form, text="Project Key").grid(row=1, column=0, sticky="w", pady=3)
            self.project_key_entry = ttk.Entry(form, width=70)
            self.project_key_entry.grid(row=1, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="JIRA Password").grid(row=2, column=0, sticky="w", pady=3)
            self.password_entry = ttk.Entry(form, width=70, show="*")
            self.password_entry.grid(row=2, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Components (comma-separated, mandatory)").grid(row=3, column=0, sticky="w", pady=3)
            self.components_entry = ttk.Entry(form, width=70)
            self.components_entry.grid(row=3, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Creation Date >= (YYYY-MM-DD, mandatory)").grid(row=4, column=0, sticky="w", pady=3)
            self.creation_date_entry = ttk.Entry(form, width=70)
            self.creation_date_entry.grid(row=4, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Desired Start Date >= (YYYY-MM-DD, mandatory)").grid(row=5, column=0, sticky="w", pady=3)
            self.desired_start_entry = ttk.Entry(form, width=70)
            self.desired_start_entry.grid(row=5, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Issue Key Filter (comma-separated)").grid(row=6, column=0, sticky="w", pady=3)
            self.issue_key_filter_entry = ttk.Entry(form, width=70)
            self.issue_key_filter_entry.grid(row=6, column=1, sticky="ew", pady=3)

            form.columnconfigure(1, weight=1)
            ttk.Button(form, text="Run Extraction", command=self.run_extraction).grid(
                row=1, column=2, padx=8, rowspan=2, sticky="ns"
            )
            ttk.Button(form, text="Apply Issue Key Filter", command=self.apply_filter).grid(
                row=3, column=2, padx=8, sticky="ew"
            )
            ttk.Button(form, text="Reset Filter", command=self.reset_filter).grid(
                row=4, column=2, padx=8, sticky="ew"
            )
        except Exception:
            logger.exception("Failed to build GUI form")
            raise

    @staticmethod
    def _parse_csv_values(raw: str) -> list[str]:
        try:
            return [part.strip() for part in raw.split(",") if part.strip()]
        except Exception:
            logger.exception("Failed to parse comma-separated values")
            raise

    def _build_tabs(self) -> None:
        try:
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

            for name in self.TABLES:
                frame = ttk.Frame(self.notebook)
                self.notebook.add(frame, text=name)

                tree = ttk.Treeview(frame, show="headings")
                scroll_y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
                scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

                tree.pack(side="left", fill="both", expand=True)
                scroll_y.pack(side="right", fill="y")
                scroll_x.pack(side="bottom", fill="x")
                self.table_views[name] = tree
        except Exception:
            logger.exception("Failed to build tabs")
            raise

    def run_extraction(self) -> None:
        try:
            project_key = self.project_key_entry.get().strip()
            password = self.password_entry.get().strip()
            components = self._parse_csv_values(self.components_entry.get().strip())
            creation_date = self.creation_date_entry.get().strip()
            desired_start_date = self.desired_start_entry.get().strip()

            if not project_key or not password or not components or not creation_date or not desired_start_date:
                raise ValueError(
                    "Project key, JIRA password, components, creation date, and desired start date are mandatory."
                )

            cfg = JiraConfig(password=password)
            query_filters = ProjectQueryFilters(
                components=components,
                created_on_or_after=creation_date,
                desired_start_on_or_after=desired_start_date,
            )

            orchestrator = JiraExtractionOrchestrator(cfg)
            self.results = orchestrator.run(project_key, query_filters)

            out_dir = cfg.downloads_output_dir()
            orchestrator.save_to_csv(self.results, out_dir)
            self.base_tables = asdict(self.results)
            self._render_all(self.base_tables)
            logger.info("Extraction succeeded for project %s", project_key)
            messagebox.showinfo("Success", f"Extraction complete. Files written to {out_dir}")
        except Exception as exc:  # pragma: no cover - ui feedback path
            logger.exception("Extraction failed")
            messagebox.showerror("Extraction Error", str(exc))

    def _render_all(self, tables: dict[str, pd.DataFrame]) -> None:
        try:
            for name, df in tables.items():
                self._render_df(self.table_views[name], df)
        except Exception:
            logger.exception("Failed to render tables")
            raise

    @staticmethod
    def _render_df(tree: ttk.Treeview, df: pd.DataFrame) -> None:
        tree.delete(*tree.get_children())

        columns = list(df.columns)
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor="w")

        for _, row in df.fillna("").iterrows():
            tree.insert("", "end", values=list(row.values))

    def apply_filter(self) -> None:
        try:
            if not self.base_tables:
                return

            raw_filter = self.issue_key_filter_entry.get().strip()
            issue_keys = {value.upper() for value in self._parse_csv_values(raw_filter)}
            if not issue_keys:
                self._render_all(self.base_tables)
                return

            filtered: dict[str, pd.DataFrame] = {}
            for name, df in self.base_tables.items():
                if df.empty:
                    filtered[name] = df
                    continue

                key_columns = [col for col in df.columns if "key" in col.lower()]
                if not key_columns:
                    filtered[name] = df
                    continue

                mask = pd.Series(False, index=df.index)
                for col in key_columns:
                    mask = mask | df[col].astype(str).str.upper().isin(issue_keys)
                filtered[name] = df[mask]

            self._render_all(filtered)
        except Exception as exc:  # pragma: no cover - ui feedback path
            logger.exception("Failed to apply issue-key filter")
            messagebox.showerror("Filter Error", str(exc))

    def reset_filter(self) -> None:
        try:
            self.issue_key_filter_entry.delete(0, tk.END)
            if self.base_tables:
                self._render_all(self.base_tables)
        except Exception as exc:  # pragma: no cover - ui feedback path
            logger.exception("Failed to reset filter")
            messagebox.showerror("Reset Error", str(exc))

    def run(self) -> None:
        try:
            logger.info("Launching GUI main loop")
            self.root.mainloop()
        except Exception:
            logger.exception("Unhandled GUI runtime exception")
            raise
