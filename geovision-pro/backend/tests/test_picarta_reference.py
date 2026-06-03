"""Unit tests for the new Picarta + reference logic (no model / network needed)."""
from app.services.picarta import parse_response
from app.services.reference import coords_from_name


def test_parse_response_topk():
    data = {
        "ai_lat": 48.8584, "ai_lon": 2.2945, "ai_country": "France", "ai_city": "Paris",
        "topk_predictions_dict": {
            "1": {"gps": [48.8584, 2.2945], "confidence": 0.62,
                  "address": {"country": "France", "city": "Paris", "province": "Île-de-France"}},
            "2": {"gps": [45.764, 4.8357], "confidence": 0.18,
                  "address": {"country": "France", "city": "Lyon"}},
        },
    }
    preds = parse_response(data)
    assert len(preds) == 2
    assert preds[0]["city"] == "Paris"
    assert preds[0]["confidence"] == 0.62
    assert abs(preds[0]["lat"] - 48.8584) < 1e-6
    assert preds[1]["city"] == "Lyon"


def test_parse_response_toplevel_fallback():
    # no topk dict -> use the single ai_* prediction
    data = {"ai_lat": 35.6895, "ai_lon": 139.6917, "ai_country": "Japan", "ai_city": "Tokyo"}
    preds = parse_response(data)
    assert len(preds) == 1
    assert preds[0]["country"] == "Japan"
    assert abs(preds[0]["lon"] - 139.6917) < 1e-6


def test_parse_response_empty():
    assert parse_response({}) == []
    assert parse_response({"topk_predictions_dict": {}}) == []
    assert parse_response(None) == []


def test_coords_from_name():
    assert coords_from_name("cafe_48.8584_2.2945.jpg") == (48.8584, 2.2945)
    assert coords_from_name("48.8584,2.2945.png") == (48.8584, 2.2945)
    # negative coordinates
    assert coords_from_name("spot_-33.8688_151.2093.jpg") == (-33.8688, 151.2093)


def test_coords_from_name_none():
    assert coords_from_name("holiday_photo.jpg") == (None, None)
    # out-of-range rejected
    assert coords_from_name("x_999.123_2.234.jpg") == (None, None)
