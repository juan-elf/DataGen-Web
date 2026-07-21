"""
Tests for the bundled sample dataset (DB-free).

The point of these is that the sample ships *inside* the image and is loaded
through the same pipeline as a real upload — so a packaging mistake or a
malformed CSV would break the demo path silently in production.
"""
from pathlib import Path

import pytest

from api.sample import DEFAULT_SAMPLE, SAMPLES_DIR, _SAMPLE_NAME_RE
from ingest.loader import load_file
from ingest.schema_infer import sanitize_columns, try_parse_dates


def _sample_path() -> Path:
    return SAMPLES_DIR / f"{DEFAULT_SAMPLE}.csv"


class TestBundledSample:
    def test_sample_file_exists(self):
        assert _sample_path().is_file(), "bundled sample CSV is missing from the image"

    def test_sample_parses_through_the_real_loader(self):
        path = _sample_path()
        result = load_file(path.name, path.read_bytes())
        assert len(result.df) > 100
        assert not result.warnings, f"sample should load cleanly, got: {result.warnings}"

    def test_sample_has_the_columns_the_demo_relies_on(self):
        path = _sample_path()
        df, _ = sanitize_columns(load_file(path.name, path.read_bytes()).df)
        for col in ("order_date", "region", "category", "quantity", "total_amount"):
            assert col in df.columns

    def test_sample_dates_are_parseable(self):
        path = _sample_path()
        df = try_parse_dates(load_file(path.name, path.read_bytes()).df)
        import pandas as pd

        assert pd.api.types.is_datetime64_any_dtype(df["order_date"])

    def test_sample_has_missing_values_to_demo_with(self):
        # One of the suggested questions is "which columns have missing values?" —
        # if the sample were perfectly clean that question would return nothing.
        path = _sample_path()
        df = load_file(path.name, path.read_bytes()).df
        assert df.isna().any().any()


class TestSampleNameGuard:
    @pytest.mark.parametrize(
        "name",
        ["../../etc/passwd", "..", "foo/bar", "foo.bar", "Foo", "foo-bar", "", "foo bar"],
    )
    def test_rejects_unsafe_dataset_names(self, name):
        assert not _SAMPLE_NAME_RE.match(name)

    @pytest.mark.parametrize("name", ["ecommerce_orders", "battery", "sales2024"])
    def test_accepts_plain_slugs(self, name):
        assert _SAMPLE_NAME_RE.match(name)
