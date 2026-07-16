from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rent_watch.config import city_by_id
from rent_watch.storage import ListingStore
from rent_watch.sources import (
    HousingAnywhereSource,
    ImmoweltSource,
    KleinanzeigenSource,
    Listing,
    listing_matches_filters,
    parse_area,
    parse_price,
    parse_rooms,
)


BERLIN = city_by_id("berlin")


class ParserTests(unittest.TestCase):
    def test_basic_number_parsing(self) -> None:
        text = "1.399 € Kaltmiete, 2 Zimmer, 61,5 m²"
        self.assertEqual(parse_price(text), 1399)
        self.assertEqual(parse_rooms(text), 2)
        self.assertEqual(parse_area(text), 61.5)

    def test_kleinanzeigen_card_context(self) -> None:
        html = """
        <article class="aditem">
          <img src="https://img.kleinanzeigen.de/api/v1/prod-ads/images/aa/example.jpg" alt="Wohnzimmer">
          <a href="/s-anzeige/helle-wohnung/123456789-203-3331">
            Helle 2 Zimmer Wohnung in Neukölln
          </a>
          <p>12043 Berlin</p>
          <p>48 m² · 2 Zi.</p>
          <p>850 €</p>
        </article>
        """
        listings = KleinanzeigenSource().parse(html, "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331", BERLIN, "apartment")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].rent_eur, 850)
        self.assertEqual(listings[0].rooms, 2)
        self.assertEqual(listings[0].area_sqm, 48)
        self.assertEqual(listings[0].listing_type, "apartment")
        self.assertEqual(listings[0].image_url, "https://img.kleinanzeigen.de/api/v1/prod-ads/images/aa/example.jpg")

    def test_immowelt_image_alt_listing(self) -> None:
        html = """
        <a href="/expose/abc123">
          <img alt="Wohnung zur Miete - Erstbezug 1.950 € 3 Zimmer 110,6 m² 1. Geschoss George-Stephenson-Straße 20 Moabit Berlin 10557">
        </a>
        """
        listings = ImmoweltSource().parse(html, "https://www.immowelt.de/suche/berlin/wohnungen/mieten", BERLIN, "apartment")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].rent_eur, 1950)
        self.assertEqual(listings[0].rooms, 3)
        self.assertEqual(listings[0].area_sqm, 110.6)
        self.assertEqual(listings[0].title, "Wohnung zur Miete - Erstbezug")

    def test_svg_paths_do_not_become_titles(self) -> None:
        html = """
        <a href="/expose/badtitle">
          <svg><path>d="M5-.086l6.776-6.327A4.42 4.42 0 0 0 20.4 9.56v-.22c0-2.032"/></svg>
          <img src="https://www.immowelt.de/image.jpg" alt="Altbau Stuck Immobilien Consult UG 835 € 1 Zimmer 32,1 m² 13587 Berlin">
        </a>
        """
        listings = ImmoweltSource().parse(html, "https://www.immowelt.de/suche/berlin/wohnungen/mieten", BERLIN, "apartment")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].title, "Altbau Stuck Immobilien Consult UG")
        self.assertEqual(listings[0].image_url, "https://www.immowelt.de/image.jpg")

    def test_housinganywhere_price_before_number(self) -> None:
        html = """
        <a href="/room/1234567">
          Tenant-verified Private room in Stromstraße, Berlin 9 m² 8 housemates €570 /month, incl. utilities
        </a>
        """
        listings = HousingAnywhereSource().parse(html, "https://housinganywhere.com/s/Berlin--Germany", BERLIN, "room")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].rent_eur, 570)
        self.assertEqual(listings[0].listing_type, "room")
        self.assertEqual(listings[0].area_sqm, 9)

    def test_wg_gesucht_numeric_listing_links(self) -> None:
        from rent_watch.sources import WGGesuchtSource

        html = """
        <div class="offer_list_item">
          <img src="/img/listing-room.jpg" alt="WG Zimmer Bild">
          <a href="/13779664.html">WG Zimmer in Berlin Wedding</a>
          <span>500 €</span><span>20 m²</span><span>1 Zimmer</span>
        </div>
        """
        listings = WGGesuchtSource().parse(html, "https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html", BERLIN, "room")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].url, "https://www.wg-gesucht.de/13779664.html")
        self.assertEqual(listings[0].title, "WG Zimmer in Berlin Wedding")
        self.assertEqual(listings[0].image_url, "https://www.wg-gesucht.de/img/listing-room.jpg")

    def test_wg_gesucht_json_ld_listing(self) -> None:
        from rent_watch.sources import WGGesuchtSource

        html = """
        <script type="application/ld+json">
        [{
          "@type": "CollectionPage",
          "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [{
              "@type": "ListItem",
              "item": {
                "@type": "RealEstateListing",
                "name": "WG Room by the Spree",
                "url": "https://www.wg-gesucht.de/wg-zimmer-in-Berlin-Tiergarten.13704244.html",
                "description": "3er WG",
                "offers": {"@type": "Room", "price": "650.00", "priceCurrency": "EUR"},
                "mainEntity": {
                  "@type": "Offer",
                  "address": {
                    "@type": "PostalAddress",
                    "postalCode": "10555",
                    "addressRegion": "Tiergarten",
                    "addressLocality": "Berlin"
                  }
                },
                "image": "https://img.wg-gesucht.de/media/up/example.small.jpg"
              }
            }]
          }
        }]
        </script>
        """
        listings = WGGesuchtSource().parse(html, "https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html", BERLIN, "room")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].title, "WG Room by the Spree")
        self.assertEqual(listings[0].rent_eur, 650)
        self.assertEqual(listings[0].location, "10555 Tiergarten Berlin")
        self.assertEqual(listings[0].image_url, "https://img.wg-gesucht.de/media/up/example.small.jpg")

    def test_listing_filters_keep_unknown_numeric_values(self) -> None:
        listing = Listing(
            source="test",
            title="Quiet furnished room",
            url="https://example.test/listing",
            city_id="berlin",
            listing_type="room",
            rent_eur=None,
            area_sqm=None,
            rooms=1,
            raw_text="quiet furnished room",
        )
        self.assertTrue(listing_matches_filters(listing, {"propertyType": "room", "maxRent": 700, "keyword": "furnished"}))
        self.assertFalse(listing_matches_filters(listing, {"propertyType": "apartment"}))

    def test_store_drops_stale_parser_artifact_titles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "rentals.sqlite3"
            store = ListingStore(db_path)
            with store._conn:
                store._conn.execute(
                    """
                    INSERT INTO listings (
                        id, source, title, url, city_id, listing_type, first_seen, last_seen, seen
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        "bad-immowelt",
                        "immowelt",
                        "5-.086l6.776-6.327A4.42 4.42 0 0 0 20.4 9.56v-.22c0-2.032-1.47",
                        "https://www.immowelt.de/expose/bad-immowelt",
                        "berlin",
                        "apartment",
                        "2026-07-16T00:00:00+00:00",
                        "2026-07-16T00:00:00+00:00",
                    ),
                )
            store._conn.close()

            cleaned_store = ListingStore(db_path)
            listings = cleaned_store.query_listings({"city": "berlin", "sources": ["immowelt"], "propertyType": "any"})
            self.assertEqual(listings, [])

    def test_account_saved_search_stores_matches_and_listing_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "rentals.sqlite3")
            user = store.create_user("Student@example.com", "verysecret")
            self.assertEqual(user["email"], "student@example.com")
            self.assertIsNotNone(store.authenticate_user("student@example.com", "verysecret"))
            token = store.create_session(user["id"])
            self.assertEqual(store.get_user_by_session(token)["email"], "student@example.com")

            search = store.create_saved_search(
                user["id"],
                "Berlin room",
                {"city": "berlin", "sources": ["wg_gesucht"], "propertyType": "room"},
            )
            listing = Listing(
                source="wg_gesucht",
                title="Quiet room near campus",
                url="https://www.wg-gesucht.de/wg-zimmer-in-Berlin.123.html",
                city_id="berlin",
                listing_type="room",
                rent_eur=620,
                location="Berlin",
            )
            store.upsert_listings([listing])
            matches = store.query_listings(search["filters"])
            new_ids = store.save_search_matches(user["id"], search["id"], matches)
            self.assertEqual(new_ids, [listing.id])

            results = store.get_saved_search_results(user["id"], search["id"])
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["is_new"])
            store.set_listing_state(
                user["id"],
                listing.id,
                {"favorite": True, "hidden": False, "status": "contacted", "note": "Ask about Anmeldung."},
            )
            updated = store.get_saved_search_results(user["id"], search["id"])[0]
            self.assertEqual(updated["account_status"], "contacted")
            self.assertTrue(updated["favorite"])
            self.assertEqual(updated["note"], "Ask about Anmeldung.")
            store.mark_search_results_seen(user["id"], search["id"])
            self.assertEqual(store.account_summary(user["id"])["unseenCount"], 0)


if __name__ == "__main__":
    unittest.main()
