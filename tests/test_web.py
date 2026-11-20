import http.client
import os
import sys
import threading
import urllib.error
import urllib.request
from urllib.parse import urlencode

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gmaps2apple  # noqa: E402
import web  # noqa: E402

PATH_URL = "https://www.google.com/maps/dir/Athens/Corinth/Patras/"


@pytest.fixture
def server():
    srv = web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network request attempted")
    monkeypatch.setattr(urllib.request, "urlopen", boom)


def post(base, value, mode="driving"):
    conn = http.client.HTTPConnection(base.split("//")[1])
    conn.request("POST", "/", urlencode({"value": value, "mode": mode}),
                 {"Content-Type": "application/x-www-form-urlencoded"})
    r = conn.getresponse()
    return r.status, r.read().decode()


def test_index_ok(server):
    with urllib.request.urlopen(server + "/") as r:
        body = r.read().decode()
        assert r.status == 200
        assert "text/html" in r.headers["Content-Type"]
    assert 'name="viewport"' in body and "Μετατροπή" in body
    assert "<script" not in body


def test_path_url_conversion(server):
    status, body = post(server, PATH_URL)
    assert status == 200
    assert "https://maps.apple.com/directions" in body
    assert body.count("<li>") >= 3
    assert "Άνοιγμα στο Apple Maps" in body


def test_malicious_input_escaped(server):
    evil = '<script>alert(1)</script> -> "><img onerror=x>'
    _, body = post(server, evil)
    assert "<script>alert(1)" not in body
    assert "<img onerror" not in body
    assert "&lt;script&gt;" in body


@pytest.mark.parametrize("url", [
    "https://evil.example/x",
    "http://maps.app.goo.gl/x",
    "https://maps.app.goo.gl@evil.example/x",
    "https://goo.gl/foo",
    "https://maps.app.goo.gl:8443/x",
])
def test_short_link_other_host_no_network(url, no_network):
    assert not web.may_resolve(url)
    result, error, _ = web.process(url, "driving")
    assert result is None and error


def test_allowed_short_link_resolves(monkeypatch):
    calls = []
    monkeypatch.setattr(gmaps2apple, "resolve_short_link",
                        lambda u, *a, **k: calls.append(u) or PATH_URL)
    for u in ("https://maps.app.goo.gl/abc", "https://goo.gl/maps/abc"):
        assert web.may_resolve(u)
        result, error, _ = web.process(u, "driving")
        assert error is None and len(result["stops"]) == 3
    assert len(calls) == 2


def test_network_error_message(monkeypatch):
    def fail(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(gmaps2apple, "resolve_short_link", fail)
    result, error, _ = web.process("https://maps.app.goo.gl/abc", "driving")
    assert result is None and "δικτύου" in error


def test_large_input_rejected(monkeypatch, server):
    monkeypatch.setattr(gmaps2apple, "convert",
                        lambda *a, **k: pytest.fail("convert called"))
    result, error, _ = web.process("a" * (web.MAX_INPUT + 1), "driving")
    assert result is None and "μεγάλη" in error
    status, _ = post(server, "A -> " + "b" * (web.MAX_INPUT + 1))
    assert status == 413
    status, _ = post(server, "x" * 100000)
    assert status == 413


def test_invalid_mode_and_bad_input():
    result, _, mode = web.process(PATH_URL, "flying")
    assert mode == "driving" and result["mode"] == "driving"
    for v in ("", "   ", "Athens"):
        result, error, _ = web.process(v, "driving")
        assert result is None and error


def test_missing_content_length(server):
    c = http.client.HTTPConnection(server.split("//")[1])
    c.putrequest("POST", "/")
    c.endheaders()
    assert c.getresponse().status == 411


def test_404(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/nope")
    assert e.value.code == 404


# --- /api/apple ---

def api_get(base, value, mode=None):
    q = {"value": value}
    if mode:
        q["mode"] = mode
    try:
        with urllib.request.urlopen(base + "/api/apple?" + urlencode(q)) as r:
            return r.status, r.headers["Content-Type"], r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers["Content-Type"], e.read().decode()


def api_post(base, value, mode="driving"):
    conn = http.client.HTTPConnection(base.split("//")[1])
    conn.request("POST", "/api/apple", urlencode({"value": value, "mode": mode}),
                 {"Content-Type": "application/x-www-form-urlencoded"})
    r = conn.getresponse()
    return r.status, r.getheader("Content-Type"), r.read().decode()


def test_api_get_path_url(server):
    status, ctype, body = api_get(server, PATH_URL)
    assert status == 200
    assert ctype == "text/plain; charset=utf-8"
    assert body.startswith("https://maps.apple.com/directions")
    assert body == body.strip() and "\n" not in body


def test_api_post_same_as_get(server):
    assert api_post(server, PATH_URL) == api_get(server, PATH_URL)


def test_api_url_inside_text(server):
    text = "Τίτλος\n" + PATH_URL + " ευχαριστώ https://example.com/x"
    assert api_get(server, text)[2] == api_get(server, PATH_URL)[2]


def test_extract_value():
    assert web.extract_value("Αθήνα -> Πάτρα") == "Αθήνα -> Πάτρα"
    assert web.extract_value("A (http://a.b/c). B https://d.e") == "http://a.b/c"


def test_api_plain_stops(server):
    status, ctype, body = api_get(server, "Αθήνα -> Πάτρα", "walking")
    assert status == 200 and body.startswith("https://maps.apple.com/")


@pytest.mark.parametrize("value", ["", "   "])
def test_api_invalid_400(server, value):
    status, ctype, body = api_get(server, value)
    assert status == 400
    assert ctype == "text/plain; charset=utf-8"
    assert body and "Traceback" not in body


def test_api_too_large_413(server):
    big = "a" * (web.MAX_INPUT + 1)
    assert api_get(server, big)[0] == 413
    assert api_post(server, big)[0] == 413


def test_api_other_host_short_link_no_network(server, no_network):
    status, _, body = api_get(server, "Δες https://evil.example/abc εδώ")
    assert status == 400 and "Traceback" not in body


def test_resolve_passes_timeout(monkeypatch):
    seen = {}

    def fake(req, *a, **kw):
        seen.update(kw)
        raise TimeoutError()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    web.process("https://maps.app.goo.gl/abc", "driving")
    assert seen.get("timeout") == 10


@pytest.mark.parametrize("exc", [TimeoutError(), urllib.error.URLError(TimeoutError())])
def test_resolve_timeout_message(monkeypatch, exc):
    def fake(*a, **kw):
        raise exc
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    result, error, _ = web.process("https://maps.app.goo.gl/abc", "driving")
    assert result is None and "άργησε" in error


def test_connection_timeout_and_parallel(monkeypatch, server):
    import socket
    import time
    assert web.Handler.timeout == 15
    monkeypatch.setattr(web.Handler, "timeout", 0.5)
    host, port = server.split("//")[1].split(":")
    idle = socket.create_connection((host, int(port)))
    try:
        assert api_get(server, PATH_URL)[0] == 200  # απαντά ενώ η idle είναι ανοιχτή
        idle.settimeout(5)
        t0 = time.time()
        assert idle.recv(1) == b""  # ο server έκλεισε τη σύνδεση
        assert time.time() - t0 < 4
    finally:
        idle.close()
