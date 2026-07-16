from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    id: str
    country: str
    name: str
    pressure_note: str
    kleinanzeigen_slug: str = ""
    kleinanzeigen_location: str = ""
    immoscout_state: str = ""
    immoscout_city: str = ""
    immowelt_slug: str = ""
    housinganywhere_slug: str = ""
    wg_slug: str = ""
    wg_city_id: int | None = None
    nl_slug: str = ""
    funda_area: str = ""


COUNTRIES: dict[str, str] = {
    "de": "Germany",
    "nl": "Netherlands",
}


CITIES: list[City] = [
    City("berlin", "de", "Berlin", "Large student market, persistent rental pressure", "berlin", "l3331", "berlin", "berlin", "berlin", "Berlin--Germany", "Berlin", 8),
    City("munich", "de", "Munich", "One of Germany's tightest and most expensive student markets", "muenchen", "l6411", "bayern", "muenchen", "muenchen", "Munich--Germany", "Muenchen", 90),
    City("hamburg", "de", "Hamburg", "Large university city with high demand", "hamburg", "l9409", "hamburg", "hamburg", "hamburg", "Hamburg--Germany", "Hamburg", 55),
    City("cologne", "de", "Cologne", "Major NRW student city with tight private market", "koeln", "l945", "nordrhein-westfalen", "koeln", "koeln", "Cologne--Germany", "Koeln", 73),
    City("frankfurt", "de", "Frankfurt am Main", "High rents and commuter demand", "frankfurt-main", "l4292", "hessen", "frankfurt-am-main", "frankfurt-am-main", "Frankfurt--Germany", "Frankfurt-am-Main", 41),
    City("stuttgart", "de", "Stuttgart", "High-income region with tight rental supply", "stuttgart", "l9280", "baden-wuerttemberg", "stuttgart", "stuttgart", "Stuttgart--Germany", "Stuttgart", 124),
    City("freiburg", "de", "Freiburg", "Classic constrained student city", "freiburg", "l9352", "baden-wuerttemberg", "freiburg-im-breisgau", "freiburg-im-breisgau", "Freiburg-im-Breisgau--Germany", "Freiburg", 43),
    City("heidelberg", "de", "Heidelberg", "Small, high-demand university city", "heidelberg", "l9182", "baden-wuerttemberg", "heidelberg", "heidelberg", "Heidelberg--Germany", "Heidelberg", 52),
    City("tuebingen", "de", "Tuebingen", "Small university city with limited stock", "tuebingen", "l9331", "baden-wuerttemberg", "tuebingen", "tuebingen", "Tuebingen--Germany", "Tuebingen", 129),
    City("muenster", "de", "Muenster", "Large student share and recurring room shortages", "muenster", "l929", "nordrhein-westfalen", "muenster", "muenster", "Muenster--Germany", "Muenster", 91),
    City("bonn", "de", "Bonn", "NRW student city with high waiting-list pressure", "bonn", "l1689", "nordrhein-westfalen", "bonn", "bonn", "Bonn--Germany", "Bonn", 17),
    City("aachen", "de", "Aachen", "RWTH-driven demand, especially at semester starts", "aachen", "l1921", "nordrhein-westfalen", "aachen", "aachen", "Aachen--Germany", "Aachen", 1),
    City("darmstadt", "de", "Darmstadt", "Tech university city with tight affordable supply", "darmstadt", "l4896", "hessen", "darmstadt", "darmstadt", "Darmstadt--Germany", "Darmstadt", 23),
    City("karlsruhe", "de", "Karlsruhe", "KIT-driven demand and limited cheap supply", "karlsruhe", "l9186", "baden-wuerttemberg", "karlsruhe", "karlsruhe", "Karlsruhe--Germany", "Karlsruhe", 68),
    City("potsdam", "de", "Potsdam", "Small market near Berlin with student housing pressure", "potsdam", "l7966", "brandenburg", "potsdam", "potsdam", "Potsdam--Germany", "Potsdam", 110),
    City("leipzig", "de", "Leipzig", "Fast-growing student city", "leipzig", "l4233", "sachsen", "leipzig", "leipzig", "Leipzig--Germany", "Leipzig", 77),
    City("amsterdam", "nl", "Amsterdam", "Largest Dutch rental market with intense student and expat demand", housinganywhere_slug="Amsterdam--Netherlands", nl_slug="amsterdam", funda_area="amsterdam"),
    City("rotterdam", "nl", "Rotterdam", "Large city with active private rental supply", housinganywhere_slug="Rotterdam--Netherlands", nl_slug="rotterdam", funda_area="rotterdam"),
    City("the-hague", "nl", "The Hague", "Government city with tight apartment and room demand", housinganywhere_slug="The-Hague--Netherlands", nl_slug="den-haag", funda_area="den-haag"),
    City("utrecht", "nl", "Utrecht", "Major student city with severe room shortages", housinganywhere_slug="Utrecht--Netherlands", nl_slug="utrecht", funda_area="utrecht"),
    City("eindhoven", "nl", "Eindhoven", "Tech and student market with rising rents", housinganywhere_slug="Eindhoven--Netherlands", nl_slug="eindhoven", funda_area="eindhoven"),
    City("groningen", "nl", "Groningen", "Large student share and recurring room shortages", housinganywhere_slug="Groningen--Netherlands", nl_slug="groningen", funda_area="groningen"),
    City("tilburg", "nl", "Tilburg", "Growing student city in Noord-Brabant", housinganywhere_slug="Tilburg--Netherlands", nl_slug="tilburg", funda_area="tilburg"),
    City("almere", "nl", "Almere", "Large commuter city near Amsterdam", housinganywhere_slug="Almere--Netherlands", nl_slug="almere", funda_area="almere"),
    City("breda", "nl", "Breda", "Popular southern student and starter market", housinganywhere_slug="Breda--Netherlands", nl_slug="breda", funda_area="breda"),
    City("nijmegen", "nl", "Nijmegen", "University city with tight affordable rooms", housinganywhere_slug="Nijmegen--Netherlands", nl_slug="nijmegen", funda_area="nijmegen"),
    City("enschede", "nl", "Enschede", "Student city with UT-driven room demand", housinganywhere_slug="Enschede--Netherlands", nl_slug="enschede", funda_area="enschede"),
    City("haarlem", "nl", "Haarlem", "Tight commuter market near Amsterdam", housinganywhere_slug="Haarlem--Netherlands", nl_slug="haarlem", funda_area="haarlem"),
    City("arnhem", "nl", "Arnhem", "Regional city with active rental market", housinganywhere_slug="Arnhem--Netherlands", nl_slug="arnhem", funda_area="arnhem"),
    City("amersfoort", "nl", "Amersfoort", "Central commuter city with limited supply", housinganywhere_slug="Amersfoort--Netherlands", nl_slug="amersfoort", funda_area="amersfoort"),
    City("zaandam", "nl", "Zaandam", "Amsterdam-area alternative with rising demand", housinganywhere_slug="Zaandam--Netherlands", nl_slug="zaandam", funda_area="zaandam"),
    City("den-bosch", "nl", "'s-Hertogenbosch", "Popular Brabant city with tight private rentals", housinganywhere_slug="Den-Bosch--Netherlands", nl_slug="den-bosch", funda_area="den-bosch"),
    City("apeldoorn", "nl", "Apeldoorn", "Large Gelderland city with broad rental stock", housinganywhere_slug="Apeldoorn--Netherlands", nl_slug="apeldoorn", funda_area="apeldoorn"),
    City("leiden", "nl", "Leiden", "University city with high student room pressure", housinganywhere_slug="Leiden--Netherlands", nl_slug="leiden", funda_area="leiden"),
    City("maastricht", "nl", "Maastricht", "International student city with strong room demand", housinganywhere_slug="Maastricht--Netherlands", nl_slug="maastricht", funda_area="maastricht"),
    City("delft", "nl", "Delft", "TU Delft market with tight student supply", housinganywhere_slug="Delft--Netherlands", nl_slug="delft", funda_area="delft"),
]


SOURCE_LABELS: dict[str, str] = {
    "kleinanzeigen": "Kleinanzeigen",
    "immoscout": "ImmoScout24",
    "immowelt": "Immowelt",
    "wg_gesucht": "WG-Gesucht",
    "housinganywhere_de": "HousingAnywhere",
    "funda": "Funda",
    "pararius": "Pararius",
    "kamernet": "Kamernet",
    "huurwoningen": "Huurwoningen.nl",
    "directwonen": "Direct Wonen",
    "housinganywhere_nl": "HousingAnywhere",
}


SOURCE_COUNTRIES: dict[str, str] = {
    "kleinanzeigen": "de",
    "immoscout": "de",
    "immowelt": "de",
    "wg_gesucht": "de",
    "housinganywhere_de": "de",
    "funda": "nl",
    "pararius": "nl",
    "kamernet": "nl",
    "huurwoningen": "nl",
    "directwonen": "nl",
    "housinganywhere_nl": "nl",
}


DEFAULT_SOURCES_BY_COUNTRY: dict[str, list[str]] = {
    "de": ["kleinanzeigen", "immowelt", "wg_gesucht", "housinganywhere_de"],
    "nl": ["funda", "pararius", "kamernet", "huurwoningen", "directwonen", "housinganywhere_nl"],
}


PROPERTY_TYPES: dict[str, str] = {
    "any": "Any rental",
    "apartment": "Apartment / studio",
    "room": "Room / shared housing",
    "house": "House",
}


def city_by_id(city_id: str) -> City:
    for city in CITIES:
        if city.id == city_id:
            return city
    raise KeyError(f"Unknown city: {city_id}")


def cities_for_country(country: str) -> list[City]:
    return [city for city in CITIES if city.country == country]
