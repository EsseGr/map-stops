import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gmaps2apple as g  # noqa: E402


def test_path_form():
    url = ("https://www.google.com/maps/dir/Athens,+Greece/Corinth/Patras,+Greece/"
           "@37.9,22.5,9z/data=!3m1!4b1")
    stops, mode = g.parse_google_url(url)
    assert stops == ["Athens, Greece", "Corinth", "Patras, Greece"]
    assert mode is None


def test_path_form_coordinates():
    stops, _ = g.parse_google_url("https://www.google.com/maps/dir/37.97,23.72/38.0,23.8/")
    assert stops == ["37.97,23.72", "38.0,23.8"]


def test_api1_form():
    url = ("https://www.google.com/maps/dir/?api=1&origin=A+St&destination=D+St"
           "&waypoints=B%20St%7CC%20St&travelmode=walking")
    stops, mode = g.parse_google_url(url)
    assert stops == ["A St", "B St", "C St", "D St"]
    assert mode == "walking"


def test_api1_no_origin():
    stops, _ = g.parse_google_url("https://www.google.com/maps/dir/?api=1&destination=X&waypoints=Y")
    assert stops == ["Y", "X"]


def test_legacy_form():
    stops, _ = g.parse_google_url("https://maps.google.com/maps?saddr=A&daddr=B+to:C+to:D")
    assert stops == ["A", "B", "C", "D"]


def test_not_directions():
    with pytest.raises(ValueError):
        g.parse_google_url("https://www.google.com/maps/place/Foo")


def test_text_inputs():
    assert g.parse_input("A -> B → C") == (["A", "B", "C"], None)
    assert g.parse_input("A\nB\n\nC\n")[0] == ["A", "B", "C"]


def test_short_link_resolved(monkeypatch):
    monkeypatch.setattr(g, "resolve_short_link",
                        lambda u: "https://www.google.com/maps/dir/A/B/C/")
    assert g.parse_input("https://maps.app.goo.gl/abc123")[0] == ["A", "B", "C"]


def test_short_link_no_network():
    with pytest.raises(ValueError):
        g.parse_input("https://maps.app.goo.gl/abc123", resolve=False)


def test_apple_url_order_and_encoding():
    url = g.apple_url(["Athens, Greece", "Corinth", "Patras"], "walking")
    assert url == ("https://maps.apple.com/directions?source=Athens%2C%20Greece"
                   "&waypoint=Corinth&destination=Patras&mode=walking")


def test_apple_url_multiple_waypoints_and_coords():
    url = g.apple_url(["37.98,23.72", "A B", "C", "38.1,21.7"])
    assert url == ("https://maps.apple.com/directions?source=37.98,23.72"
                   "&waypoint=A%20B&waypoint=C&destination=38.1,21.7&mode=driving")
    assert "daddr" not in url


def test_apple_url_two_stops_no_waypoint():
    url = g.apple_url(["A", "B"], "bicycling")
    assert url == "https://maps.apple.com/directions?source=A&destination=B&mode=cycling"


def test_apple_legs():
    legs = g.apple_legs(["A", "B", "C"])
    assert legs == ["https://maps.apple.com/?saddr=A&daddr=B&dirflg=d",
                    "https://maps.apple.com/?saddr=B&daddr=C&dirflg=d"]


def test_too_few_stops():
    with pytest.raises(ValueError):
        g.apple_url(["A"])


def test_cli_json(capsys):
    rc = g.main(["https://www.google.com/maps/dir/A/B/C/", "--no-resolve", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["stops"] == ["A", "B", "C"]
    assert len(out["legs"]) == 2
    assert out["apple_url"].startswith("https://maps.apple.com/directions?source=A&waypoint=B")


def test_cli_error(capsys):
    assert g.main(["https://example.com/x", "--no-resolve"]) == 1
