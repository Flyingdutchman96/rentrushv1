from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    id: str
    name: str
    pressure_note: str
    kleinanzeigen_slug: str
    kleinanzeigen_location: str
    immoscout_state: str
    immoscout_city: str
    immowelt_slug: str
    housinganywhere_slug: str
    wg_slug: str
    wg_city_id: int | None


CITIES: list[City] = [
    City("berlin", "Berlin", "Large student market, persistent rental pressure", "berlin", "l3331", "berlin", "berlin", "berlin", "Berlin--Germany", "Berlin", 8),
    City("munich", "Munich", "One of Germany's tightest and most expensive student markets", "muenchen", "l6411", "bayern", "muenchen", "muenchen", "Munich--Germany", "Muenchen", 90),
    City("hamburg", "Hamburg", "Large university city with high demand", "hamburg", "l9409", "hamburg", "hamburg", "hamburg", "Hamburg--Germany", "Hamburg", 55),
    City("cologne", "Cologne", "Major NRW student city with tight private market", "koeln", "l945", "nordrhein-westfalen", "koeln", "koeln", "Cologne--Germany", "Koeln", 73),
    City("frankfurt", "Frankfurt am Main", "High rents and commuter demand", "frankfurt-main", "l4292", "hessen", "frankfurt-am-main", "frankfurt-am-main", "Frankfurt--Germany", "Frankfurt-am-Main", 41),
    City("stuttgart", "Stuttgart", "High-income region with tight rental supply", "stuttgart", "l9280", "baden-wuerttemberg", "stuttgart", "stuttgart", "Stuttgart--Germany", "Stuttgart", 124),
    City("freiburg", "Freiburg", "Classic constrained student city", "freiburg", "l9352", "baden-wuerttemberg", "freiburg-im-breisgau", "freiburg-im-breisgau", "Freiburg-im-Breisgau--Germany", "Freiburg", 43),
    City("heidelberg", "Heidelberg", "Small, high-demand university city", "heidelberg", "l9182", "baden-wuerttemberg", "heidelberg", "heidelberg", "Heidelberg--Germany", "Heidelberg", 52),
    City("tuebingen", "Tuebingen", "Small university city with limited stock", "tuebingen", "l9331", "baden-wuerttemberg", "tuebingen", "tuebingen", "Tuebingen--Germany", "Tuebingen", 129),
    City("muenster", "Muenster", "Large student share and recurring room shortages", "muenster", "l929", "nordrhein-westfalen", "muenster", "muenster", "Muenster--Germany", "Muenster", 91),
    City("bonn", "Bonn", "NRW student city with high waiting-list pressure", "bonn", "l1689", "nordrhein-westfalen", "bonn", "bonn", "Bonn--Germany", "Bonn", 17),
    City("aachen", "Aachen", "RWTH-driven demand, especially at semester starts", "aachen", "l1921", "nordrhein-westfalen", "aachen", "aachen", "Aachen--Germany", "Aachen", 1),
    City("darmstadt", "Darmstadt", "Tech university city with tight affordable supply", "darmstadt", "l4896", "hessen", "darmstadt", "darmstadt", "Darmstadt--Germany", "Darmstadt", 23),
    City("karlsruhe", "Karlsruhe", "KIT-driven demand and limited cheap supply", "karlsruhe", "l9186", "baden-wuerttemberg", "karlsruhe", "karlsruhe", "Karlsruhe--Germany", "Karlsruhe", 68),
    City("potsdam", "Potsdam", "Small market near Berlin with student housing pressure", "potsdam", "l7966", "brandenburg", "potsdam", "potsdam", "Potsdam--Germany", "Potsdam", 110),
    City("leipzig", "Leipzig", "Fast-growing student city", "leipzig", "l4233", "sachsen", "leipzig", "leipzig", "Leipzig--Germany", "Leipzig", 77),
]


SOURCE_LABELS: dict[str, str] = {
    "kleinanzeigen": "Kleinanzeigen",
    "immoscout": "ImmoScout24",
    "immowelt": "Immowelt",
    "wg_gesucht": "WG-Gesucht",
    "housinganywhere": "HousingAnywhere",
}


PROPERTY_TYPES: dict[str, str] = {
    "any": "Any rental",
    "apartment": "Apartment / studio",
    "room": "Room / WG",
    "house": "House",
}


def city_by_id(city_id: str) -> City:
    for city in CITIES:
        if city.id == city_id:
            return city
    raise KeyError(f"Unknown city: {city_id}")

