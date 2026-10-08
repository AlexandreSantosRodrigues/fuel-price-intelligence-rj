from pathlib import Path

from src.quality.raw_audit import EXPECTED_COLUMNS, audit_csv, detect_csv_format


def create_sample_csv(path: Path) -> None:
    header = ";".join(EXPECTED_COLUMNS)

    rows = [
        (
            "SUDESTE;RJ;RIO DE JANEIRO;POSTO EXEMPLO;"
            "00.000.000/0001-00;RUA A;10;;CENTRO;20000-000;"
            "GASOLINA;01/01/2025;6,29;;R$ / litro;BRANCA"
        ),
        (
            "SUDESTE;RJ;RIO DE JANEIRO;POSTO EXEMPLO;"
            "00.000.000/0001-00;RUA A;10;;CENTRO;20000-000;"
            "GASOLINA;01/01/2025;6,29;;R$ / litro;BRANCA"
        ),
        (
            "SUDESTE;RJ;NITEROI;POSTO TESTE;"
            "11.111.111/0001-11;RUA B;20;;ICARAI;24000-000;"
            "ETANOL;02/01/2025;4,39;;R$ / litro;RAIZEN"
        ),
    ]

    content = header + "\n" + "\n".join(rows) + "\n"
    path.write_text(content, encoding="utf-8-sig")


def test_detect_csv_format(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    create_sample_csv(csv_path)

    result = detect_csv_format(csv_path)

    assert result["encoding"] == "utf-8-sig"
    assert result["separator"] == ";"
    assert result["column_count"] == 16


def test_audit_csv_counts_rows_nulls_and_duplicates(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    create_sample_csv(csv_path)

    result = audit_csv(csv_path)

    assert result["row_count"] == 3
    assert result["duplicate_rows"] == 1
    assert result["null_counts"]["Valor de Compra"] == 3
    assert result["null_counts"]["Complemento"] == 3


def test_audit_csv_validates_schema(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    create_sample_csv(csv_path)

    result = audit_csv(csv_path)

    assert result["schema_valid"] is True
    assert result["missing_columns"] == []
    assert result["unexpected_columns"] == []
    