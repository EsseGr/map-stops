# Plan: Google Maps route -> Apple Maps multi-stop

Goal: take a Google Maps route (origin, N intermediate stops, destination) and
reproduce the same ordered stops in Apple Maps. Easiest path first: no native
app, usable from an iPhone or a simple web page.

Legend: **[V]** verified in a doc/page I read this session, **[C]** community
report only, **[A]** assumed / from memory, must be tested on a real iPhone.

## 1. What Apple Maps supports

| Mechanism | Multi-stop via link/API? | Status |
|---|---|---|
| `maps.apple.com/?saddr=&daddr=&dirflg=` | Single destination documented. Repeating `daddr` (or `to:` inside `daddr`) for extra stops is reported to work. | [C] ABRP bug thread reports repeated `daddr`; `to:` syntax is [A]. Apple's own doc page (developer.apple.com, "Adopting unified Maps URLs" / legacy Map Links) could not be read by my fetcher (JS-rendered), so the absence/presence of waypoints in the official doc is **unverified**. |
| Same link shared from iOS | The ABRP thread says multi-stop routes shared from iOS only show directions to the first stop. | [C] |
| Maps app UI "Add Stop" (iOS 16+, up to 15 stops) | Yes, manual. No auto-reorder. | [C] (iMore, AppleInsider, TechRepublic) |
| maps.apple.com on the web (beta) | User says it allows adding stops. | [A] from user, not checked |
| MapKit `MKDirections.Request` / MapKit JS | Single source + destination; Apple Developer Forums thread asks about multi-stop with no confirmed answer. | [C] forum thread, no official answer seen. Also needs a developer account/token for MapKit JS. |
| iOS Shortcuts | Workaround: open URL to set destination, then a search URL for the next stop and tap "Add Stop". Not fully automatic. | [C] r/shortcuts thread |
| Apple Maps Guides | Curated lists of places, not routes. Guides can be created in-app (iOS 17+). Not a route format. | [A] |

Bottom line: no officially documented multi-stop link was found. The
repeated-`daddr` link is the only candidate and **must be tested first** on the
target iPhone (does it open all stops, in order, as a route?).

## 2. Parsing Google Maps URLs

- **Short links** `maps.app.goo.gl/XXXX`: HTTP redirect to a long
  `google.com/maps/...` URL. [A] (no source found describing it). Needs an
  HTTP request that follows redirects, so a browser-only page is blocked by CORS
  and needs a tiny proxy/serverless function; Shortcuts ("Get Contents of URL" /
  "Expand URL") can do it on-device. [A]
- **Documented API format** `google.com/maps/dir/?api=1&origin=&destination=&waypoints=a|b|c`
  [V]: waypoints are `|`-separated, in order, each a name, address or `lat,lng`;
  Google's own limit is 3 on mobile browsers and 9 elsewhere; `*_place_id`
  params exist. These links are trivial to parse, no key needed.
- **Path format** `google.com/maps/dir/Origin/Stop1/Stop2/Dest/@lat,lng,zoom/data=...`
  [A, widely seen, not in the official doc]: stops are URL-encoded path
  segments between `/dir/` and `/@`, in order. Each can be text or `lat,lng`.
  Order is preserved. No key needed to extract the text.
- **`data=` param**: protobuf-like, `!`-separated tokens, each `<id><type><value>`
  [V: github.com/nexces/google-maps-data-parameter-parser]. Meaning of
  `!1d` (lng) / `!2d` (lat) per waypoint, `!1s` (place id/name) and `!3e` (travel
  mode) is [A] from an example URL; not documented. Use only to get coordinates when
  the path segments are names; treat as best-effort.
- Without an API key: names and coordinates from path/`data=` are enough, as
  Apple Maps can geocode text. Resolving a place-id-only stop or a
  `/maps/place/...` link to coordinates would need Google Places (key) or
  Apple's geocoder (MapKit, token). Avoid in v1.
- Edge cases: `via:` waypoints (not stopovers), stops typed by hand (plain text
  geocoded by Apple), unknown N (cap at Apple's 15; warn above that).

## 3. Options, ranked by ease

1. **Web page + generated link (easiest, no app).** Static page: paste Google
   links/text, resolve short links (needs small proxy, or ask the user to paste
   the long URL), parse stops, build an Apple Maps link with repeated `daddr`,
   show it as a tappable link. Limits: depends on the unverified multi-`daddr`
   behaviour; short-link resolution needs a server function; geocoding is by
   Apple at open time and may pick a wrong place for ambiguous names.
2. **iOS Shortcut.** Input: shared Google link. Expand URL, parse with regex,
   build the Apple Maps URL and open it. Runs on the iPhone, no hosting, handles
   short links natively. Limits: Shortcuts is clunky to build, regex fragile,
   and if multi-`daddr` fails, the fallback is a loop that opens the first
   stop and asks the user to tap "Add Stop" for the rest.
3. **Semi-manual fallback.** Page/Shortcut outputs the ordered list of stops
   (copyable) plus one Apple Maps search link per stop; user adds each with
   "Add Stop" in the Maps app (max 15). Always works, slowest, 100% order control.

## 4. Recommendation

1. Step 0 (10 minutes, before any code): on the iPhone, open
   `https://maps.apple.com/?saddr=A&daddr=B&daddr=C&dirflg=d` and a variant with
   `daddr=B+to:C`; record whether all stops appear, in order. Also test from
   Safari and from a Shared/Messages link.
2. If it works: build Option 1 (static page + one serverless redirect resolver,
   or paste-long-URL only for v1). Parse the `/dir/` path first, then
   `?api=1` params, then `data=` coordinates as fallback.
3. If it does not work: ship Option 3 as the output of the same parser (stop
   list + per-stop links); optionally wrap it as Option 2 later.

Open questions: Which stop formats appear in the user's real links (names vs
coordinates vs place IDs)? Is a tiny hosted redirect resolver acceptable?

## Sources
- Google Maps URLs, directions action: https://developers.google.com/maps/documentation/urls/get-started
- `data=` parser README: https://github.com/nexces/google-maps-data-parameter-parser
- ABRP multi-stop sharing thread: https://abrp.upvoty.com/b/report-a-bug/sharing-route-with-multiple-stops-on-ios-only-shows-directions-to-first-stop/
- Apple Developer Forums, multiple waypoints in MapKit: https://developer.apple.com/forums/thread/724907
- r/shortcuts multi-stop thread (Sep 2022): https://lr.sudovanilla.org/r/shortcuts/comments/xnpdg9/apple_maps_multistop_directions/iqx6ijj/?context=3
- iMore, add multiple stops: https://www.imore.com/how-add-multiple-stops-maps-app-iphone
- Apple "Adopting unified Maps URLs" (not readable by my fetcher; unverified): https://developer.apple.com/documentation/mapkit/unified-map-urls
