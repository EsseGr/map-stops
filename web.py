"""Μικρή σελίδα web για το gmaps2apple (μόνο standard library)."""
import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import gmaps2apple

MAX_INPUT = 4096  # bytes (UTF-8) της εισόδου του χρήστη
MAX_BODY = 4 * MAX_INPUT  # το percent-encoding των ελληνικών τριπλασιάζει το μέγεθος
MODES = ("driving", "walking", "transit")
MODE_LABELS = {"driving": "Οδήγηση", "walking": "Περπάτημα", "transit": "Μέσα μεταφοράς"}
APPLE_PREFIX = "https://maps.apple.com/"

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
    "Cache-Control": "no-store",
}

CSS = """
body{font-family:-apple-system,system-ui,sans-serif;margin:0;padding:16px;background:#f2f2f7;color:#111}
main{max-width:640px;margin:0 auto}
h1{font-size:1.5rem}
textarea,select{width:100%;box-sizing:border-box;font-size:1.1rem;padding:12px;margin:6px 0 14px;
border:1px solid #bbb;border-radius:10px}
textarea{min-height:8em}
.btn{display:block;width:100%;box-sizing:border-box;text-align:center;font-size:1.3rem;font-weight:600;
padding:18px;border:0;border-radius:14px;background:#007aff;color:#fff;text-decoration:none;margin:14px 0}
.err{background:#ffe5e5;border:1px solid #d33;border-radius:10px;padding:12px;margin:14px 0}
.card{background:#fff;border-radius:12px;padding:8px 16px;margin:14px 0}
li{margin:8px 0}
a.leg{font-size:1.05rem;word-break:break-all}
"""


def may_resolve(value):
    """Δίκτυο επιτρέπεται μόνο για https://maps.app.goo.gl/... και https://goo.gl/maps..."""
    try:
        p = urlparse(value.strip())
        if p.scheme != "https" or p.username is not None or p.password is not None:
            return False
        if p.port is not None:
            return False
        host = (p.hostname or "").lower()
        if host != (p.netloc or "").lower():
            return False
        if host == "maps.app.goo.gl":
            return True
        return host == "goo.gl" and (p.path == "/maps" or p.path.startswith("/maps/"))
    except ValueError:
        return False


def process(value, mode):
    """Επιστρέφει (result, error, mode). Ποτέ exception για είσοδο χρήστη."""
    if mode not in MODES:
        mode = "driving"
    value = value or ""
    if len(value.encode("utf-8")) > MAX_INPUT:
        return None, "Η είσοδος είναι πολύ μεγάλη (μέγιστο 4 KB).", mode
    if not value.strip():
        return None, "Επικόλλησε έναν σύνδεσμο Google Maps ή στάσεις χωρισμένες με «->».", mode
    try:
        result = gmaps2apple.convert(value.strip(), resolve=may_resolve(value), mode=mode)
    except ValueError as exc:
        if "resolving" in str(exc):
            return None, ("Οι σύντομοι σύνδεσμοι επιτρέπονται μόνο από https://maps.app.goo.gl/ "
                          "ή https://goo.gl/maps. Άνοιξε τον σύνδεσμο και επικόλλησε τον πλήρη."), mode
        return None, "Δεν κατάλαβα την είσοδο: %s" % exc, mode
    except OSError:
        return None, "Αποτυχία δικτύου στο άνοιγμα του συνδέσμου. Δοκίμασε τον πλήρη σύνδεσμο.", mode
    except Exception:
        return None, "Αδυναμία μετατροπής της εισόδου.", mode
    return result, None, mode


def _e(text):
    return html.escape(str(text), quote=True)


def _safe_apple(url):
    return _e(url) if str(url).startswith(APPLE_PREFIX) else "#"


def render_page(result=None, error=None, value="", mode="driving"):
    opts = "".join(
        '<option value="%s"%s>%s</option>' % (m, " selected" if m == mode else "", MODE_LABELS[m])
        for m in MODES)
    parts = [
        '<!doctype html><html lang="el"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>map-stops</title><style>%s</style></head><body><main>" % CSS,
        "<h1>Google Maps → Apple Maps</h1>",
        '<form method="post" action="/">'
        '<label for="v">Σύνδεσμος Google Maps ή στάσεις (Αθήνα -&gt; Κόρινθος -&gt; Πάτρα)</label>'
        '<textarea id="v" name="value" required>%s</textarea>'
        '<label for="m">Τρόπος μετακίνησης</label><select id="m" name="mode">%s</select>'
        '<button class="btn" type="submit">Μετατροπή</button></form>' % (_e(value), opts),
    ]
    if error:
        parts.append('<div class="err" role="alert">%s</div>' % _e(error))
    if result:
        parts.append('<div class="card"><h2>Στάσεις</h2><ol>%s</ol></div>'
                     % "".join("<li>%s</li>" % _e(s) for s in result["stops"]))
        parts.append('<a class="btn" href="%s">Άνοιγμα στο Apple Maps</a>'
                     % _safe_apple(result["apple_url"]))
        parts.append('<div class="card"><h2>iOS κάτω από 18.4</h2>'
                     "<p>Άνοιξε τα σκέλη με τη σειρά:</p><ol>%s</ol></div>" % "".join(
                         '<li><a class="leg" href="%s">Σκέλος %d</a></li>' % (_safe_apple(u), i)
                         for i, u in enumerate(result["legs"], 1)))
    parts.append("</main></body></html>")
    return "".join(parts)


class Handler(BaseHTTPRequestHandler):
    server_version = "map-stops"

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _page(self, code, **kw):
        self._send(code, render_page(**kw))

    def do_GET(self):
        if urlparse(self.path).path == "/":
            self._page(200)
        else:
            self._send(404, "Δεν βρέθηκε", "text/plain; charset=utf-8")

    def do_POST(self):
        if urlparse(self.path).path != "/":
            self._send(404, "Δεν βρέθηκε", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length"))
            if length < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.close_connection = True
            self._page(411, error="Λείπει ή είναι άκυρο το Content-Length.")
            return
        if length > MAX_BODY:
            self.close_connection = True
            self._page(413, error="Η είσοδος είναι πολύ μεγάλη (μέγιστο 4 KB).")
            return
        body = self.rfile.read(length)
        form = parse_qs(body.decode("utf-8", errors="replace"))
        value = (form.get("value") or [""])[0]
        mode = (form.get("mode") or ["driving"])[0]
        result, error, mode = process(value, mode)
        if len(value.encode("utf-8")) > MAX_INPUT:
            code = 413
        else:
            code = 400 if error else 200
        self._page(code, result=result, error=error, value=value[:MAX_INPUT], mode=mode)

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(os.environ.get("PORT", "8096"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("map-stops στο http://0.0.0.0:%d" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
