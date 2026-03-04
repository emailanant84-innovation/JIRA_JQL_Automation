from __future__ import annotations

import re

import pandas as pd


class DataCleaner:
    """Clean textual noise and deduplicate records across output dataframes."""

    _ws_pattern = re.compile(r"\s+")
    _page_break_pattern = re.compile(r"[\x0c\x0b]")

    @classmethod
    def clean_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = cls._page_break_pattern.sub(" ", value)
        cleaned = cls._ws_pattern.sub(" ", cleaned)
        return cleaned.strip()

    @classmethod
    def clean_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        for col in out.columns:
            out[col] = out[col].map(cls.clean_text)
        out = out.drop_duplicates(ignore_index=True)
        return out
