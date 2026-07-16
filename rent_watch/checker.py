from __future__ import annotations

from datetime import datetime, timezone

from .config import DEFAULT_SOURCES_BY_COUNTRY, SOURCE_COUNTRIES, SOURCE_LABELS, city_by_id
from .sources import SOURCES, SourceStatus, dedupe_listings
from .storage import ListingStore


DEFAULT_SOURCES = DEFAULT_SOURCES_BY_COUNTRY["de"]


class RentalChecker:
    def __init__(self, store: ListingStore) -> None:
        self.store = store

    def run(self, filters: dict) -> dict:
        city_id = filters.get("city") or "berlin"
        city = city_by_id(city_id)
        default_sources = DEFAULT_SOURCES_BY_COUNTRY.get(city.country, DEFAULT_SOURCES)
        selected_sources = [
            source
            for source in filters.get("sources", default_sources)
            if source in SOURCES and SOURCE_COUNTRIES.get(source) == city.country
        ]
        filters = {**filters, "city": city_id, "sources": selected_sources}

        existing_before = self.store.count_existing(city_id, selected_sources)
        all_listings = []
        statuses: list[SourceStatus] = []

        for source_key in selected_sources:
            source = SOURCES[source_key]
            result = source.search(city, filters)
            all_listings.extend(result.listings)
            statuses.extend(result.statuses or [SourceStatus(source_key, True, "No URLs for selected filters", 0)])

        all_listings = dedupe_listings(all_listings)
        new_ids = self.store.upsert_listings(all_listings)
        listings = self.store.query_listings(filters)

        new_id_set = set(new_ids)
        for listing in listings:
            listing["is_new"] = listing["id"] in new_id_set
            listing["source_label"] = SOURCE_LABELS.get(listing["source"], listing["source"])

        return {
            "city": city.name,
            "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "baseline": existing_before == 0 and bool(all_listings),
            "fetched": len(all_listings),
            "newCount": len(new_ids),
            "newListingIds": new_ids,
            "listings": listings,
            "statuses": [status.to_dict() for status in statuses],
        }
