import pandas as pd

from ingest.schema_infer import (
    infer_postgres_types,
    sanitize_columns,
    sanitize_table_name,
    try_parse_dates,
)


class TestSanitizeTableName:
    def test_lowercases_and_strips_extension_like_chars(self):
        assert sanitize_table_name("My Sales Data") == "my_sales_data"

    def test_reserved_word_gets_suffixed(self):
        assert sanitize_table_name("select") == "select_col"

    def test_leading_digit_gets_prefixed(self):
        name = sanitize_table_name("2024_sales")
        assert name[0].isalpha() or name[0] == "_"

    def test_empty_falls_back(self):
        # falls back to "table", which is itself a reserved word -> suffixed
        assert sanitize_table_name("???") == "table_col"


class TestSanitizeColumns:
    def test_renames_to_safe_identifiers(self):
        df = pd.DataFrame({"First Name": [1], "Order #": [2]})
        out, mapping = sanitize_columns(df)
        # "order" is a reserved SQL keyword -> suffixed to "order_col"
        assert list(out.columns) == ["first_name", "order_col"]
        assert mapping.safe_to_original["first_name"] == "First Name"

    def test_deduplicates_collisions(self):
        df = pd.DataFrame({"A B": [1], "A-B": [2]})
        out, _ = sanitize_columns(df)
        assert len(set(out.columns)) == len(out.columns)
        assert list(out.columns) == ["a_b", "a_b_1"]

    def test_preserves_row_data(self):
        df = pd.DataFrame({"Value ($)": [10, 20, 30]})
        out, _ = sanitize_columns(df)
        assert out["value"].tolist() == [10, 20, 30]


class TestInferPostgresTypes:
    def test_integer_column(self):
        df = pd.DataFrame({"n": [1, 2, 3]})
        assert infer_postgres_types(df)["n"] == "BIGINT"

    def test_float_column(self):
        df = pd.DataFrame({"n": [1.5, 2.5]})
        assert infer_postgres_types(df)["n"] == "DOUBLE PRECISION"

    def test_text_column(self):
        df = pd.DataFrame({"n": ["a", "b"]})
        assert infer_postgres_types(df)["n"] == "TEXT"

    def test_bool_column(self):
        df = pd.DataFrame({"n": [True, False]})
        assert infer_postgres_types(df)["n"] == "BOOLEAN"


class TestTryParseDates:
    def test_parses_iso_date_column(self):
        df = pd.DataFrame({"created_at": ["2024-01-01", "2024-01-02", "2024-01-03"]})
        out = try_parse_dates(df)
        assert pd.api.types.is_datetime64_any_dtype(out["created_at"])

    def test_leaves_non_date_text_alone(self):
        df = pd.DataFrame({"name": ["alice", "bob", "carol"]})
        out = try_parse_dates(df)
        assert not pd.api.types.is_datetime64_any_dtype(out["name"])
