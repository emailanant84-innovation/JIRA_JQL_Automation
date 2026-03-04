from __future__ import annotations

import tkinter as tk
from dataclasses import asdict
from tkinter import messagebox, ttk

import pandas as pd

from .config import JiraConfig
from .normalizer import NormalizedJiraData
from .orchestrator import JiraExtractionOrchestrator


class JiraExtractionGUI:
    """Tkinter GUI to orchestrate extraction and inspect normalized tables."""

    TABLES = ["issues", "hierarchy", "links", "labels", "components", "fix_versions"]

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("JIRA Project Extractor")
        self.root.geometry("1200x760")

        self.results: NormalizedJiraData | None = None
        self.table_views: dict[str, ttk.Treeview] = {}
        self.base_tables: dict[str, pd.DataFrame] = {}

        self._build_form()
        self._build_tabs()

    def _build_form(self) -> None:
        form = ttk.Frame(self.root, padding=10)
        form.pack(fill="x")

        labels = ["JIRA URL", "Email", "API Token", "Project Key", "Output Folder"]
        self.inputs: dict[str, tk.Entry] = {}

        for i, text in enumerate(labels):
            ttk.Label(form, text=text).grid(row=i, column=0, sticky="w", pady=3)
            entry = ttk.Entry(form, width=90, show="*" if text == "API Token" else "")
            entry.grid(row=i, column=1, sticky="ew", pady=3)
            self.inputs[text] = entry

        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="Run Extraction", command=self.run_extraction).grid(
            row=0, column=2, padx=8, rowspan=2, sticky="ns"
        )
        ttk.Button(form, text="Apply Filter", command=self.apply_filter).grid(
            row=2, column=2, padx=8, sticky="ew"
        )
        ttk.Button(form, text="Reset", command=self.reset_filter).grid(
            row=3, column=2, padx=8, sticky="ew"
        )

        self.filter_var = tk.StringVar()
        ttk.Label(form, text="Issue key/type filter").grid(row=4, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.filter_var).grid(row=5, column=2, sticky="ew")

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
            cfg = JiraConfig(
                base_url=self.inputs["JIRA URL"].get().strip(),
                email=self.inputs["Email"].get().strip(),
                api_token=self.inputs["API Token"].get().strip(),
            )
            project_key = self.inputs["Project Key"].get().strip()
            out_dir = self.inputs["Output Folder"].get().strip() or "output"

            orchestrator = JiraExtractionOrchestrator(cfg)
            self.results = orchestrator.run(project_key)
            orchestrator.save_to_csv(self.results, out_dir)
            self.base_tables = asdict(self.results)
            self._render_all(self.base_tables)
            messagebox.showinfo("Success", f"Extraction complete. Files written to {out_dir}")
        except Exception as exc:  # pragma: no cover - ui feedback path
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
            tree.column(col, width=150, anchor="w")

        for _, row in df.fillna("").iterrows():
            tree.insert("", "end", values=list(row.values))

    def apply_filter(self) -> None:
        if not self.base_tables:
            return
        needle = self.filter_var.get().strip().lower()
        if not needle:
            self._render_all(self.base_tables)
            return

        filtered: dict[str, pd.DataFrame] = {}
        for name, df in self.base_tables.items():
            if df.empty:
                filtered[name] = df
                continue

            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                if "key" in col.lower() or "type" in col.lower():
                    mask = mask | df[col].astype(str).str.lower().str.contains(needle, na=False)
            filtered[name] = df[mask]

        self._render_all(filtered)

    def reset_filter(self) -> None:
        self.filter_var.set("")
        if self.base_tables:
            self._render_all(self.base_tables)

    def run(self) -> None:
        self.root.mainloop()
