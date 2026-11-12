"""Convert a Google Maps multi-stop route into Apple Maps links.

Input: a Google Maps URL (or plain text, one stop per line / "A -> B -> C").
Output: an ordered list of stops plus Apple Maps URLs:
  * one URL with repeated ``daddr`` (community-reported, NOT officially documented)
  * one URL per leg (``saddr`` + ``daddr``), the conservative fallback.
"""
import argparse
import json
import re
import sys
import urllib.request
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
COORD_RE = re.compile(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$")
MODES = {"driving": "d", "walking": "w", "transit": "r", "bicycling": None}


def is_short_link(url):
    host = urlparse(url).netloc.lower()
    return host in SHORT_HOSTS or (host == "goo.gl")


def resolve_short_link(url, timeout=10):
    """Follow HTTP redirects and return the final URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "map-stops/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl()


def _clean(stop):
    return re.sub(r"\s+", " ", stop).strip()


def _split_legacy(value):
    """Legacy daddr style: 'A to:B to:C'."""
    return [_clean(p) for p in re.split(r"\s+to:", value) if _clean(p)]


def parse_google_url(url):
    """Return (stops, travelmode or None) from a resolved Google Maps URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    mode = (qs.get("travelmode") or [None])[0]

    # api=1 form
    if "destination" in qs or "origin" in qs or "waypoints" in qs:
        stops = []
        if qs.get("origin"):
            stops.append(_clean(qs["origin"][0]))
        if qs.get("waypoints"):
            stops += [_clean(w) for w in qs["waypoints"][0].split("|") if w.strip()]
        if qs.get("destination"):
            stops.append(_clean(qs["destination"][0]))
        return stops, mode

    # legacy saddr/daddr form
    if "daddr" in qs:
        stops = []
        if qs.get("saddr"):
            stops += _split_legacy(qs["saddr"][0])
        for d in qs["daddr"]:
            stops += _split_legacy(d)
        return stops, mode

    # path form: /maps/dir/A/B/C/@lat,lng,zoom/data=...
    segs = parsed.path.split("/")
    if "dir" in segs:
        stops = []
        for seg in segs[segs.index("dir") + 1:]:
            if seg.startswith("@") or seg.startswith("data="):
                break
            if seg:
                stops.append(_clean(unquote_plus(seg)))
        return stops, mode

    raise ValueError("Not a recognised Google Maps directions URL: %s" % url)


def parse_text(text):
    """Plain text: one stop per line, or 'A -> B -> C' / 'A | B | C'."""
    text = text.strip()
    if "\n" in text:
        parts = text.splitlines()
    else:
        parts = re.split(r"\s*(?:->|→|\|)\s*", text)
    return [_clean(p) for p in parts if _clean(p)]


def parse_input(value, resolve=True):
    """Accept a URL (short or long) or plain text; return (stops, mode)."""
    value = value.strip()
    if re.match(r"^https?://", value):
        if is_short_link(value):
            if not resolve:
                raise ValueError("Short link needs resolving (network).")
            value = resolve_short_link(value)
        return parse_google_url(value)
    return parse_text(value), None


def _apple_param(stop):
    return quote_plus(stop)


def apple_url(stops, mode=None):
    """Single URL with repeated daddr (unofficial multi-stop form)."""
    if len(stops) < 2:
        raise ValueError("Need at least origin and destination.")
    parts = ["saddr=" + _apple_param(stops[0])]
    parts += ["daddr=" + _apple_param(s) for s in stops[1:]]
    flag = MODES.get(mode or "driving")
    if flag:
        parts.append("dirflg=" + flag)
    return "https://maps.apple.com/?" + "&".join(parts)


def apple_legs(stops, mode=None):
    """One URL per leg: the fallback chain, each uses only documented params."""
    if len(stops) < 2:
        raise ValueError("Need at least origin and destination.")
    flag = MODES.get(mode or "driving")
    urls = []
    for a, b in zip(stops, stops[1:]):
        parts = ["saddr=" + _apple_param(a), "daddr=" + _apple_param(b)]
        if flag:
            parts.append("dirflg=" + flag)
        urls.append("https://maps.apple.com/?" + "&".join(parts))
    return urls


def convert(value, resolve=True, mode=None):
    stops, found_mode = parse_input(value, resolve=resolve)
    mode = mode or found_mode
    return {
        "stops": stops,
        "mode": mode or "driving",
        "apple_url": apple_url(stops, mode),
        "legs": apple_legs(stops, mode),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="Google Maps URL or text ('A -> B -> C'); '-' reads stdin")
    ap.add_argument("--no-resolve", action="store_true", help="never touch the network")
    ap.add_argument("--mode", choices=sorted(MODES), help="override travel mode")
    ap.add_argument("--json", action="store_true", help="print JSON")
    args = ap.parse_args(argv)
    value = sys.stdin.read() if args.input == "-" else args.input
    try:
        result = convert(value, resolve=not args.no_resolve, mode=args.mode)
    except (ValueError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("Stops:")
    for i, s in enumerate(result["stops"], 1):
        print("  %d. %s" % (i, s))
    print("\nSingle link (repeated daddr, unverified on iOS):")
    print("  " + result["apple_url"])
    print("\nLeg-by-leg links (fallback):")
    for i, u in enumerate(result["legs"], 1):
        print("  %d. %s" % (i, u))
    return 0


if __name__ == "__main__":
    sys.exit(main())
