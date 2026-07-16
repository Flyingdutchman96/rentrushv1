# German Rental Watch

A small local MVP that checks major German rental portals for new apartments, WG rooms, and houses in high-pressure student cities. It runs with the Python standard library only: no npm install, no paid APIs, no browser extension.

## Run

```bash
python3 server.py
```

Open http://127.0.0.1:8080, choose filters, click **Check now**, then **Start watching**. The first successful scan creates a baseline. Later scans trigger an in-app notice and, if enabled, a browser desktop notification.

Watching now runs on the local server, not in the browser tab. Once started, the server keeps scanning every 30 seconds while `server.py` is running, even if the page is closed. Reopen the page to see the latest server-side result.

## Optional Accounts

The app works without an account. Users can also create a local account with an email and password to:

- save named searches
- store every matching listing for each saved search
- keep saved searches watching in the background while the server is running
- receive browser notifications for new saved-search matches
- mark stored results as seen
- favorite, hide, status-tag, and privately note listings

Passwords are hashed with PBKDF2 and sessions use HTTP-only cookies. Account data is stored in the same local SQLite database at `data/rentals.sqlite3`.

The first account on a fresh database is an admin account. If existing accounts are present and none is admin yet, the oldest account is promoted during startup. You can also set `RENT_WATCH_ADMIN_EMAILS=owner@example.com,admin@example.com` before starting the server to mark specific accounts as admins.

Admins see an operational dashboard with user counts, saved-search counts, stored matches, source coverage, recent users, saved searches, and watcher health.

## Covered Sources

The selected country controls which source checkboxes are available. German searches only use German portals. Netherlands searches only use Dutch/international portals configured for the Netherlands.

### Germany

- Kleinanzeigen
- ImmoScout24
- Immowelt
- WG-Gesucht
- HousingAnywhere

### Netherlands

- Funda
- Pararius
- Kamernet
- Huurwoningen.nl
- Direct Wonen
- HousingAnywhere

The app fetches only normal public search-result pages, stores the first seen timestamp in `data/rentals.sqlite3`, and reports per-source failures in the UI. Some portals change markup or block automated requests; when that happens, the affected source is shown as unhealthy while the other sources continue to work.

## Filters

- City preset
- Source selection
- Apartment / WG room / house
- Max rent
- Minimum rooms
- Minimum square meters
- Keyword
- Poll interval, defaulting to 30 seconds

Unknown numeric values are kept instead of hidden so the app does not miss listings just because a portal omitted a field from its search page.

The listing display no longer has a fixed 120-result cap. It shows all matching rows currently stored in SQLite for the selected filters.

Listings show a small portal-hosted thumbnail when the source provides one. If an image URL is missing or blocked by the portal, the UI falls back to a compact source/type tile instead of downloading or storing images locally.

Rent is stored as the first price the portal exposes in its public listing data.

## Tests

```bash
python3 -m unittest
```

## Notes

This is a local personal watcher, not a bulk crawler. Keep polling intervals reasonable. For the most reliable alerts, also use the portals' own saved-search alerts where available, especially for logged-in or paywalled features.
