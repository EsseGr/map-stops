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

- Η επίσημη τεκμηρίωση Map Links (developer.apple.com) περιγράφει `saddr`, `daddr`, `dirflg`.
  **Δεν αναφέρει ενδιάμεσες στάσεις ούτε επαναλαμβανόμενο `daddr`.** Δεν βρήκα επίσημο `to:`.
- Το Open Radar 36500783 (2018) ζητά ενδιάμεσα waypoints στο URL handler· εμφανίζεται ανοιχτό.
  Μπορεί να είναι παλιό.
- Αναφορές χρηστών (ABRP bug report, Reddit r/shortcuts 2022) δείχνουν
  `maps://?saddr=..&daddr=A&daddr=B&dirflg=d` να φορτώνει πολλές στάσεις. Δεν είναι
  τεκμηριωμένο και ένα τουλάχιστον report τιτλοφορείται "shows directions to first stop",
  άρα **ανεπιβεβαίωτο** και πιθανώς μόνο η πρώτη στάση.
- Η εφαρμογή Apple Maps από iOS 16 επιτρέπει χειροκίνητα πολλαπλές στάσεις (αναφέρεται
  όριο 15, μόνο οδήγηση), όχι όμως μέσω επίσημου URL. Δεν είναι διαθέσιμο σε όλες τις χώρες.
- Shortcuts: δεν βρήκα επιβεβαιωμένη δυνατότητα να φτιαχτεί πλήρης διαδρομή. Η κοινότητα
  χρησιμοποιεί αλυσίδα Open URL (πρώτος προορισμός, μετά αναζήτηση για "Add Stop"). Guides: δεν
  διαβάζονται αξιόπιστα από Shortcuts. MapKit απαιτεί εφαρμογή iOS, εκτός πεδίου.

**Συμπέρασμα:** Το Apple Maps δεν τεκμηριώνει σύνδεσμο με πολλές στάσεις. Το εργαλείο δίνει:
1. έναν σύνδεσμο με επαναλαμβανόμενο `daddr` (δοκιμάστε πρώτα· ανεπιβεβαίωτο),
2. εναλλακτικά **αλυσίδα συνδέσμων ανά σκέλος** `saddr=Α&daddr=Β`, που χρησιμοποιεί μόνο τις
   τεκμηριωμένες παραμέτρους. Ανοίγετε το κάθε σκέλος με τη σειρά.

Ανεπιβεβαίωτο: αν ο σύνδεσμος 1 δουλεύει σε τρέχον iOS, πόσες στάσεις δέχεται, και πώς
συμπεριφέρεται το Apple Maps με συντεταγμένες ως `daddr` (υπάρχουν forum threads για regression).

### Πηγές

- https://developers.google.com/maps/documentation/urls/get-started
- https://developer.apple.com/library/prerelease/ios/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html
- https://openradar.appspot.com/36500783
- https://abrp.upvoty.com/b/report-a-bug/sharing-route-with-multiple-stops-on-ios-only-shows-directions-to-first-stop/
- https://www.reddit.com/r/shortcuts/comments/xnpdg9/apple_maps_multistop_directions/
- https://www.techrepublic.com/article/apple-maps-multiple-stops/
- https://developer.apple.com/forums/thread/784030

## Περιορισμοί

Δεν υπάρχει geocoding (προαιρετικό· δεν υλοποιήθηκε). Τα ονόματα περνούν ως κείμενο αναζήτησης στο Apple Maps.
