"""Spatial data unit tests."""

from pipeline.spatial import _parse_height, _parse_fsr, _parse_lot_size, _parse_acid_sulfate_class


def test_parse_height():
    assert _parse_height("J - 14 Metres") == 14.0
    assert _parse_height("K - 9 Metres") == 9.0
    assert _parse_height("AA - 110 Metres") == 110.0
    assert _parse_height(None) is None
    assert _parse_height("") is None


def test_parse_fsr():
    assert _parse_fsr("N - 0.6:1") == 0.6
    assert _parse_fsr("T - 2.5:1") == 2.5
    assert _parse_fsr("A - 1:1") == 1.0
    assert _parse_fsr(None) is None
    assert _parse_fsr("") is None


def test_parse_lot_size():
    assert _parse_lot_size("450 square metres") == 450.0
    assert _parse_lot_size("700") == 700.0
    assert _parse_lot_size(None) is None


def test_parse_acid_sulfate():
    assert _parse_acid_sulfate_class("Class 3") == 3
    assert _parse_acid_sulfate_class("Class 5") == 5
    assert _parse_acid_sulfate_class(None) is None
