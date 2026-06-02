"""Unit tests for pure logic that does NOT require the vision model."""
from app.services.labels import COUNTRY_TO_CONTINENT, COUNTRY_NAMES
from app.services.ocr import candidate_queries


def test_continent_mapping_complete():
    assert all(c in COUNTRY_TO_CONTINENT for c in COUNTRY_NAMES)
    assert COUNTRY_TO_CONTINENT["Germany"] == "Europe"
    assert COUNTRY_TO_CONTINENT["Japan"] == "Asia"


def test_candidate_queries_extracts_lines():
    text = "Hotel Bellevue\nZermatt\n!!\nab"
    q = candidate_queries(text)
    assert any("Zermatt" in s for s in q)
    # the joined query of meaningful lines should be first
    assert "Hotel Bellevue" in q[0]
