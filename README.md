# map-stops

Created 12/11/2026 on the Pi (cg-init). Work happens on `pi/*` branches; `main` is merged by Manolis on GitHub.

Μετατρέπει διαδρομή Google Maps με ενδιάμεσες στάσεις σε συνδέσμους Apple Maps (iPhone).
Python 3, μόνο standard library, χωρίς API keys.

## Χρήση

```
python3 gmaps2apple.py "https://www.google.com/maps/dir/Athens/Corinth/Patras/"
python3 gmaps2apple.py "https://maps.app.goo.gl/XXXX"          # κάνει resolve το redirect (δίκτυο)
python3 gmaps2apple.py "Athens -> Corinth -> Patras" --mode walking
python3 gmaps2apple.py "<url>" --no-resolve --json
```

Η έξοδος περιέχει: (1) τη λίστα στάσεων, (2) έναν σύνδεσμο με επαναλαμβανόμενο `daddr`
(ανεπιβεβαίωτος, βλ. παρακάτω), (3) έναν σύνδεσμο ανά σκέλος (το συντηρητικό fallback).

Ως module: `import gmaps2apple; gmaps2apple.convert(url)` -> dict με `stops`, `apple_url`, `legs`.

Tests: `python3 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/python -m pytest`
(offline, χωρίς δίκτυο).

## Έρευνα

Πηγές: αναζητήσεις web και ανάγνωση της τεκμηρίωσης Google Maps URLs. Δεν έχω iPhone,
οπότε καμία συμπεριφορά του Apple Maps δεν έχει δοκιμαστεί πρακτικά.

### Μορφές συνδέσμων Google Maps

| Μορφή | Παράδειγμα | Parsing | Κατάσταση |
|---|---|---|---|
| Path | `google.com/maps/dir/A/B/C/@lat,lng,z/data=...` | τμήματα μετά το `dir`, μέχρι `@...` ή `data=`; url-decode | υλοποιημένο |
| `api=1` (επίσημο) | `maps/dir/?api=1&origin=&destination=&waypoints=B\|C&travelmode=` | `waypoints` χωρισμένα με `\|`, με τη σειρά | υλοποιημένο· όριο 3 στάσεις σε mobile browser, 9 αλλού (τεκμηρίωση Google) |
| Legacy | `maps?saddr=A&daddr=B+to:C` | `to:` ως διαχωριστικό | υλοποιημένο |
| Short link | `maps.app.goo.gl/...` | HTTP redirect προς μία από τις παραπάνω μορφές | υλοποιημένο (urllib ακολουθεί redirects)· δεν δοκιμάστηκε με πραγματικό link |
| My Maps / κοινόχρηστοι χάρτες | `google.com/maps/d/...?mid=` | δεν είναι διαδρομή· θα χρειαζόταν export KML | **δεν υποστηρίζεται** |

Σημειώσεις: στο path form κενό τμήμα (τρέχουσα τοποθεσία) αγνοείται. Συντεταγμένες στο
`!1d..!2d..` του `data=` δεν διαβάζονται, μόνο τα ονόματα του path. Αν το Google κάνει
consent redirect για short link, το resolve θα αποτύχει.

### Apple Maps και πολλαπλές στάσεις

Αποτέλεσμα δοκιμής στο iPhone (Manolis):

- **Πολλά `daddr`** (`?saddr=A&daddr=B&daddr=C`): **δεν δουλεύει**. Κρατιέται μόνο το πρώτο
  `daddr`, οι υπόλοιπες στάσεις χάνονται. Η έξοδος αυτή έχει αφαιρεθεί.
- **`directions?source=A&waypoint=B&waypoint=C&destination=D&mode=driving`**: **δουλεύει** και
  δείχνει σωστά και τις 3 στάσεις. Απαιτεί **iOS 18.4+**. Κάθε ενδιάμεση στάση είναι ξεχωριστό
  `waypoint`, με τη σειρά της διαδρομής. Τεκμηρίωση (unified map URLs):
  https://developer.apple.com/documentation/mapkit/unified-map-urls

Το εργαλείο δίνει:
1. **κύριο σύνδεσμο** σε αυτό το format (κείμενα URL-encoded, συντεταγμένες ως `lat,lon`),
2. **αλυσίδα συνδέσμων ανά σκέλος** `saddr=Α&daddr=Β`, ως εναλλακτική για iOS παλαιότερο από
   18.4. Ανοίγετε το κάθε σκέλος με τη σειρά.

Ανεπιβεβαίωτο: μέγιστος αριθμός waypoints.

### Πηγές

- https://developers.google.com/maps/documentation/urls/get-started
- https://developer.apple.com/library/prerelease/ios/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html
- https://openradar.appspot.com/36500783
- https://abrp.upvoty.com/b/report-a-bug/sharing-route-with-multiple-stops-on-ios-only-shows-directions-to-first-stop/
- https://www.reddit.com/r/shortcuts/comments/xnpdg9/apple_maps_multistop_directions/
- https://www.techrepublic.com/article/apple-maps-multiple-stops/
- https://developer.apple.com/forums/thread/784030
- https://developer.apple.com/documentation/mapkit/unified-map-urls

## Περιορισμοί

Δεν υπάρχει geocoding (προαιρετικό· δεν υλοποιήθηκε). Τα ονόματα περνούν ως κείμενο αναζήτησης στο Apple Maps.
