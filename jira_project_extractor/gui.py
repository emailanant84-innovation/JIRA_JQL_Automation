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

    TABLES = [
        "primary_issues",
        "child_issues",
        "subtask_issues",
        "linked_issues",
    ]

    def __init__(self) -> None:
        try:
            self.root = tk.Tk()
            self.root.title("JIRA Project Extractor")
            self.root.geometry("1400x860")

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

            ttk.Label(form, text="Issue Type (mandatory, e.g. Epic/Feature/Task)").grid(row=3, column=0, sticky="w", pady=3)
            self.issue_type_entry = ttk.Entry(form, width=70)
            self.issue_type_entry.grid(row=3, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Components (comma-separated, optional)").grid(row=4, column=0, sticky="w", pady=3)
            self.components_entry = ttk.Entry(form, width=70)
            self.components_entry.grid(row=4, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Creation Date Start (YYYY-MM-DD, mandatory)").grid(row=5, column=0, sticky="w", pady=3)
            self.creation_start_entry = ttk.Entry(form, width=70)
            self.creation_start_entry.grid(row=5, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Creation Date End (YYYY-MM-DD, mandatory)").grid(row=6, column=0, sticky="w", pady=3)
            self.creation_end_entry = ttk.Entry(form, width=70)
            self.creation_end_entry.grid(row=6, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Resolution Date Start (YYYY-MM-DD, optional)").grid(row=7, column=0, sticky="w", pady=3)
            self.resolution_start_entry = ttk.Entry(form, width=70)
            self.resolution_start_entry.grid(row=7, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Resolution Date End (YYYY-MM-DD, optional)").grid(row=8, column=0, sticky="w", pady=3)
            self.resolution_end_entry = ttk.Entry(form, width=70)
            self.resolution_end_entry.grid(row=8, column=1, sticky="ew", pady=3)

            ttk.Label(form, text="Issue Key Filter (comma-separated, optional)").grid(row=9, column=0, sticky="w", pady=3)
            self.issue_key_filter_entry = ttk.Entry(form, width=70)
            self.issue_key_filter_entry.grid(row=9, column=1, sticky="ew", pady=3)
            self.issue_key_filter_entry.bind("<KeyRelease>", lambda _: self.apply_filter())

            form.columnconfigure(1, weight=1)
            ttk.Button(form, text="Run Extraction", command=self.run_extraction, width=22).grid(
                row=1, column=2, padx=8, sticky="ew"
            )
            ttk.Button(form, text="Reset Filter", command=self.reset_filter, width=22).grid(
                row=2, column=2, padx=8, sticky="ew"
            )
        except Exception:
            logger.exception("Failed to build GUI form")
            raise

    @staticmethod
    def _parse_csv_values(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(",") if part.strip()]

    def _build_tabs(self) -> None:
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

    def run_extraction(self) -> None:
        try:
            project_key = self.project_key_entry.get().strip()
            password = self.password_entry.get().strip()
            issue_type = self.issue_type_entry.get().strip()
            components = self._parse_csv_values(self.components_entry.get().strip())
            creation_start_date = self.creation_start_entry.get().strip()
            creation_end_date = self.creation_end_entry.get().strip()
            resolution_start_date = self.resolution_start_entry.get().strip()
            resolution_end_date = self.resolution_end_entry.get().strip()

            if not project_key or not password or not issue_type or not creation_start_date or not creation_end_date:
                raise ValueError("Project key, password, issue type, and creation start/end dates are mandatory.")

            cfg = JiraConfig(password=password)
            query_filters = ProjectQueryFilters(
                components=components,
                created_start_date=creation_start_date,
                created_end_date=creation_end_date,
                resolution_start_date=resolution_start_date,
                resolution_end_date=resolution_end_date,
                issue_type=issue_type,
            )

            orchestrator = JiraExtractionOrchestrator(cfg)
            self.results = orchestrator.run(project_key, query_filters)

            out_dir = cfg.downloads_output_dir()
            orchestrator.save_to_csv(self.results, out_dir)
            self.base_tables = asdict(self.results)
            self.apply_filter()
            messagebox.showinfo("Success", f"Extraction complete. Files written to {out_dir}")
        except Exception as exc:  # pragma: no cover
            logger.exception("Extraction failed")
            messagebox.showerror("Extraction Error", str(exc))

    def _render_all(self, tables: dict[str, pd.DataFrame]) -> None:
        for name, df in tables.items():
            self._render_df(self.table_views[name], df)

    @staticmethod
    def _render_df(tree: ttk.Treeview, df: pd.DataFrame) -> None:
        tree.delete(*tree.get_children())
        columns = list(df.columns)
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=170, anchor="w")
        for _, row in df.fillna("").iterrows():
            tree.insert("", "end", values=list(row.values))

    def apply_filter(self) -> None:
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

    def reset_filter(self) -> None:
        for entry in [
            self.project_key_entry,
            self.password_entry,
            self.issue_type_entry,
            self.components_entry,
            self.creation_start_entry,
            self.creation_end_entry,
            self.resolution_start_entry,
            self.resolution_end_entry,
            self.issue_key_filter_entry,
        ]:
            entry.delete(0, tk.END)

        self.base_tables = {}
        for name in self.TABLES:
            self._render_df(self.table_views[name], pd.DataFrame())

    def run(self) -> None:
        self.root.mainloop()
