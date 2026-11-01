import pandas as pd

from app.unit_metadata import agriculture_economics_unit_status


def _metadata(tmp_path, **overrides):
    row = {
        "dataset": "Agriculture statistics",
        "area_unit": "hectare",
        "production_unit": "tonne",
        "yield_unit": "tonne per hectare",
        "evidence_source": "Official source data dictionary, table 2",
        "verification_status": "verified",
    }
    row.update(overrides)
    path = tmp_path / "source_metadata.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def test_pending_units_block_economic_conversion(tmp_path):
    path = _metadata(tmp_path, verification_status="pending")

    supported, message = agriculture_economics_unit_status(path)

    assert not supported
    assert "disabled" in message


def test_supported_verified_units_enable_conversion(tmp_path):
    supported, _ = agriculture_economics_unit_status(_metadata(tmp_path))

    assert supported


def test_verified_but_unsupported_units_do_not_enable_conversion(tmp_path):
    path = _metadata(tmp_path, area_unit="thousand hectares")

    supported, message = agriculture_economics_unit_status(path)

    assert not supported
    assert "supports only" in message
