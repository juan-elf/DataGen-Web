import pytest

from ingest.loader import LoadError, MAX_COLUMNS, MAX_ROWS, MAX_UPLOAD_BYTES, load_file


class TestLoadFileCSV:
    def test_parses_simple_csv(self):
        raw = b"a,b,c\n1,2,3\n4,5,6\n"
        result = load_file("data.csv", raw)
        assert list(result.df.columns) == ["a", "b", "c"]
        assert len(result.df) == 2

    def test_skips_bad_lines_instead_of_raising(self):
        raw = b"a,b\n1,2\n3,4,5,6\n7,8\n"
        result = load_file("data.csv", raw)
        assert len(result.df) >= 2

    def test_latin1_fallback(self):
        raw = "a,b\ncafé,2\n".encode("latin-1")
        result = load_file("data.csv", raw)
        assert len(result.df) == 1

    def test_empty_file_rejected(self):
        with pytest.raises(LoadError):
            load_file("data.csv", b"a,b\n")

    def test_unsupported_extension_rejected(self):
        with pytest.raises(LoadError):
            load_file("data.txt", b"a,b\n1,2\n")

    def test_too_large_rejected(self):
        raw = b"a\n" + b"1\n" * 10
        with pytest.raises(LoadError):
            load_file("data.csv", raw[: -1] + b"x" * (MAX_UPLOAD_BYTES + 1))

    def test_too_many_columns_rejected(self):
        header = ",".join(f"c{i}" for i in range(MAX_COLUMNS + 1))
        row = ",".join(str(i) for i in range(MAX_COLUMNS + 1))
        raw = f"{header}\n{row}\n".encode()
        with pytest.raises(LoadError):
            load_file("data.csv", raw)

    def test_row_overflow_truncates_with_warning(self):
        header = "a\n"
        rows = "\n".join(str(i) for i in range(MAX_ROWS + 10))
        raw = (header + rows + "\n").encode()
        result = load_file("data.csv", raw)
        assert len(result.df) == MAX_ROWS
        assert result.warnings
