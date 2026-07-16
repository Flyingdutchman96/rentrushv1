from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha1
from html import unescape
from html.parser import HTMLParser
import json
import re
import time
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .config import City, SOURCE_LABELS


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 14
MAX_LISTINGS_PER_SOURCE = 30
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP_TAGS = {"script", "style", "noscript", "svg"}


@dataclass
class Listing:
    source: str
    title: str
    url: str
    city_id: str
    listing_type: str
    rent_eur: int | None = None
    area_sqm: float | None = None
    rooms: float | None = None
    location: str | None = None
    image_url: str | None = None
    raw_text: str = ""

    @property
    def id(self) -> str:
        return sha1(f"{self.source}|{self.url}".encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        item = asdict(self)
        item["id"] = self.id
        item["source_label"] = SOURCE_LABELS.get(self.source, self.source)
        return item


@dataclass
class SourceStatus:
    source: str
    ok: bool
    message: str
    fetched: int = 0
    url: str | None = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_label": SOURCE_LABELS.get(self.source, self.source),
            "ok": self.ok,
            "message": self.message,
            "fetched": self.fetched,
            "url": self.url,
        }


@dataclass
class SourceResult:
    listings: list[Listing]
    statuses: list[SourceStatus]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        if self.skip_depth:
            return
        if tag in {"br", "p", "div", "li", "tr", "article", "section", "h1", "h2", "h3"}:
            self.parts.append(" ")
        if tag == "img":
            attrs_dict = dict(attrs)
            alt = attrs_dict.get("alt")
            if alt:
                self.parts.append(f" {alt} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if not self.skip_depth and tag in {"a", "p", "div", "li", "tr", "article", "section"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.current: dict[str, str | list[str]] | None = None
        self.depth = 0
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "a" and attrs_dict.get("href"):
            self.current = {"href": attrs_dict["href"] or "", "parts": []}
            self.depth = 1
            return
        if self.current is not None:
            if tag == "img" and attrs_dict.get("alt"):
                self.current["parts"].append(attrs_dict["alt"] or "")  # type: ignore[index,union-attr]
            if tag in VOID_TAGS:
                return
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if self.current is None:
            return
        self.depth -= 1
        if self.depth <= 0:
            text = clean_text(" ".join(self.current["parts"]))  # type: ignore[index]
            self.anchors.append({"href": self.current["href"], "text": text})  # type: ignore[index]
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None and not self.skip_depth:
            self.current["parts"].append(data)  # type: ignore[index,union-attr]


def clean_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def html_to_text(fragment: str) -> str:
    parser = TextExtractor()
    parser.feed(fragment)
    return clean_text(" ".join(parser.parts))


def strip_tracking_noise(text: str) -> str:
    text = re.sub(r"\b(Image|Bild|Foto):\s*", "", text, flags=re.I)
    text = re.sub(r"\b(Neu|New|Top|TOP|Gesponsert|Sponsored|Projekteinheit|Bauprojekt|Vorschau)\b\s*[0-9]*", " ", text)
    text = re.sub(r"\b(Immowelt logo|Anbieterlogo|Zum Projekt|zum Projekt)\b", " ", text, flags=re.I)
    text = re.sub(r"\b(Tenant-verified|Verified|Anzeige|Online-Besichtigung|360°?\s*Tour|Video)\b", " ", text, flags=re.I)
    return clean_text(text)


def strip_vector_noise(text: str) -> str:
    tokens = clean_text(text.replace('">', " ")).split()
    output: list[str] = []
    run: list[str] = []

    def is_vectorish(token: str) -> bool:
        compact = token.strip("\"'`.,;:()[]{}")
        if len(compact) < 6:
            return False
        if "€" in compact or "m²" in compact or "m2" in compact.lower():
            return False
        digit_count = sum(char.isdigit() for char in compact)
        if digit_count < 3:
            return False
        if re.fullmatch(r"[A-Za-z]?-?[0-9]+(?:\.[0-9]+)?(?:[-,][A-Za-z]?[0-9]+(?:\.[0-9]+)?)*[A-Za-z]?", compact):
            return True
        return len(compact) > 18 and digit_count / max(len(compact), 1) > 0.45 and any(char in compact for char in ".-")

    def flush_run() -> None:
        nonlocal run
        if len(run) < 6:
            output.extend(run)
        run = []

    for token in tokens:
        if is_vectorish(token):
            run.append(token)
            continue
        flush_run()
        output.append(token)
    flush_run()
    return clean_text(" ".join(output))


def parse_number(value: str) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    value = value.replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    else:
        parts = value.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            value = "".join(parts)
    try:
        return float(value)
    except ValueError:
        return None


def parse_price(text: str) -> int | None:
    patterns = [
        r"(?:€|EUR)\s*([0-9][0-9.\s]*(?:,[0-9]{1,2})?)",
        r"([0-9][0-9.\s]*(?:,[0-9]{1,2})?)\s*(?:€|EUR)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            amount = parse_number(match.group(1))
            if amount is None:
                continue
            if 80 <= amount <= 20000:
                return int(round(amount))
    return None


def parse_area(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:[,.][0-9]+)?)\s*(?:m²|m2|qm|sq\.?\s*m)", text, flags=re.I)
    if not match:
        return None
    area = parse_number(match.group(1))
    if area is None or area <= 0 or area > 1000:
        return None
    return round(area, 1)


def parse_rooms(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:[,.][0-9]+)?)\s*(?:Zi\.?|Zimmer|rooms?)\b", text, flags=re.I)
    if match:
        rooms = parse_number(match.group(1))
        if rooms is not None and 0 < rooms <= 20:
            return rooms
    if re.search(r"\b(private room|shared room|wg-zimmer|zimmer in)\b", text, flags=re.I):
        return 1.0
    return None


def infer_listing_type(text: str, fallback: str = "any") -> str:
    haystack = text.lower()
    if re.search(r"\b(haus|house|reihenhaus|doppelhaushälfte|doppelhaushaelfte)\b", haystack):
        return "house"
    if any(token in haystack for token in ["wohnung", "apartment", "studio", "flat", "maisonette"]):
        return "apartment"
    if any(token in haystack for token in ["wg-zimmer", "private room", "shared room", "student residence", "room in", "zimmer"]):
        return "room"
    return fallback if fallback != "any" else "apartment"


def title_from_text(text: str) -> str:
    text = strip_vector_noise(strip_tracking_noise(text))
    text = re.sub(r"^[0-9]+(?:\.[0-9]+)?\s+", "", text)
    text = re.sub(r"^(?:ab|from)\s+", "", text, flags=re.I)
    text = re.sub(r"\b[0-9]+(?:[,.][0-9]+)?\s*(?:housemates?|Mitbewohner(?:in|innen)?|Bewohner)\b", " ", text, flags=re.I)
    text = re.split(r"(?:€|EUR)\s*[0-9]|[0-9][0-9.\s]*(?:,[0-9]{1,2})?\s*(?:€|EUR)", text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"(?:\s+[·|]\s*|\s{2,})[0-9]+(?:[,.][0-9]+)?\s*(?:m²|m2|qm|Zi\.?|Zimmer)\b.*$", "", text, flags=re.I)
    text = re.sub(r"\b(?:Kaltmiete|Warmmiete|Gesamtmiete|incl\. utilities|inkl\. Nebenkosten).*$", "", text, flags=re.I)
    text = re.sub(
        r"^.+?\b((?:Wohnung|Studio|Apartment|Zimmer|Haus|WG-Zimmer)\s+zur\s+Miete(?:\s*-\s*[^€]+)?)\b.*$",
        r"\1",
        text,
        flags=re.I,
    )
    text = clean_text(text)
    if len(text) > 140:
        text = text[:137].rstrip() + "..."
    return text or "Rental listing"


def title_is_bad(title: str) -> bool:
    title = clean_text(title)
    if len(title) < 5:
        return True
    if any(marker in title for marker in ["<", ">", "{", "}"]):
        return True
    if re.search(r"(?:[a-zA-Z]-?[0-9]+(?:\.[0-9]+)?){4,}", title):
        return True
    numeric_tokens = re.findall(r"-?[0-9]+(?:\.[0-9]+)?", title)
    if len(numeric_tokens) >= 8:
        return True
    if title.lower() in {"image", "foto", "bild", "logo", "anbieterlogo"}:
        return True
    return False


def best_title(*candidates: str) -> str:
    cleaned: list[str] = []
    for candidate in candidates:
        if not clean_text(candidate):
            continue
        title = title_from_text(candidate)
        if title != "Rental listing" and not title_is_bad(title):
            cleaned.append(title)
    if cleaned:
        cleaned.sort(key=lambda item: (len(item) < 12, len(item)))
        return cleaned[0]
    return "Rental listing"


def location_from_text(text: str, city: City) -> str:
    text = strip_vector_noise(text)
    post_code = re.search(r"\b([0-9]{5})\b(?:\s+([A-ZÄÖÜ][A-Za-zäöüßÄÖÜ\-]+(?:\s+[A-ZÄÖÜ][A-Za-zäöüßÄÖÜ\-]+)?))?", text)
    if post_code:
        postcode = post_code.group(1)
        district = post_code.group(2) or ""
        district = re.sub(r"\b(?:wohnung|apartment|studio|zimmer|haus|miete|zur)\b.*$", "", district, flags=re.I)
        tail = clean_text(f"{postcode} {district}")
        if tail:
            return tail
    for sep in [" Berlin", " Hamburg", " Muenchen", " Munich", " Cologne", " Koeln", " Frankfurt", " Stuttgart", " Freiburg", " Heidelberg", " Tuebingen", " Muenster", " Bonn", " Aachen", " Darmstadt", " Karlsruhe", " Potsdam", " Leipzig"]:
        if sep.strip().lower() in text.lower():
            return city.name
    return city.name


def absolute_url(base_url: str, href: str) -> str:
    href = clean_text(href)
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


def normalize_image_url(base_url: str, value: str | None) -> str | None:
    if not value:
        return None
    value = clean_text(value)
    if not value or value.startswith("data:"):
        return None
    if "," in value and " " in value:
        value = value.split(",")[0].split()[0]
    elif " " in value:
        value = value.split()[0]
    url = absolute_url(base_url, value)
    if not url.startswith(("http://", "https://")):
        return None
    if any(token in url.lower() for token in ["logo", "icon", "avatar", "sprite", "placeholder"]):
        return None
    url = re.sub(r"([?&])h=50\b", r"\1h=160", url)
    url = re.sub(r"([?&])w=50\b", r"\1w=160", url)
    return url


def extract_first_image_url(block: str, base_url: str) -> str | None:
    for img_match in re.finditer(r"<img\b[^>]*>", block, flags=re.I | re.S):
        tag = img_match.group(0)
        attrs = dict((name.lower(), unescape(value)) for name, value in re.findall(r"([:\w-]+)\s*=\s*['\"]([^'\"]+)['\"]", tag))
        alt = clean_text(attrs.get("alt", ""))
        if re.search(r"\b(logo|icon|avatar|premium|schufa|male|female|männlich|weiblich)\b", alt, flags=re.I):
            continue
        for attr in ["src", "data-src", "data-lazy-src", "data-imgsrc", "srcset", "data-srcset"]:
            image_url = normalize_image_url(base_url, attrs.get(attr))
            if image_url:
                return image_url
    return None


def image_alt_text(block: str) -> str:
    alts = []
    for img_match in re.finditer(r"<img\b[^>]*>", block, flags=re.I | re.S):
        tag = img_match.group(0)
        attrs = dict((name.lower(), unescape(value)) for name, value in re.findall(r"([:\w-]+)\s*=\s*['\"]([^'\"]+)['\"]", tag))
        alt = clean_text(attrs.get("alt", ""))
        if re.search(r"\b(logo|icon|avatar|premium|schufa|male|female|männlich|weiblich)\b", alt, flags=re.I):
            continue
        if re.search(r"\b(bild|foto|image|picture)\b", alt, flags=re.I) and len(alt) < 32:
            continue
        if alt:
            alts.append(alt)
    return " ".join(alts)


def context_fragment_for_href(html: str, href: str, radius: int = 2600) -> str:
    candidates = [href, href.replace("&", "&amp;"), href.replace("&amp;", "&")]
    index = -1
    for candidate in candidates:
        index = html.find(candidate)
        if index >= 0:
            break
    if index < 0:
        return ""
    start = max(0, index - radius // 2)
    end = min(len(html), index + radius)
    return html[start:end]


def context_for_href(html: str, href: str, radius: int = 2600) -> str:
    return html_to_text(context_fragment_for_href(html, href, radius))


def collect_listing_anchors(
    html: str,
    base_url: str,
    predicate: Callable[[str], bool],
) -> list[dict[str, str]]:
    parser = AnchorCollector()
    parser.feed(html)
    seen: set[str] = set()
    cards: list[dict[str, str]] = []
    for anchor in parser.anchors:
        href = anchor["href"]
        url = absolute_url(base_url, href)
        if url in seen or not predicate(url):
            continue
        seen.add(url)
        fragment = context_fragment_for_href(html, href)
        cards.append(
            {
                "url": url,
                "anchor_text": anchor.get("text", ""),
                "context": html_to_text(fragment),
                "image_text": image_alt_text(fragment),
                "image_url": extract_first_image_url(fragment, base_url),
            }
        )
    return cards


def collect_listing_cards_from_blocks(
    html: str,
    base_url: str,
    block_pattern: str,
    predicate: Callable[[str], bool],
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for block_match in re.finditer(block_pattern, html, flags=re.I | re.S):
        block = block_match.group(0)
        parser = AnchorCollector()
        parser.feed(block)
        candidates = []
        for anchor in parser.anchors:
            url = absolute_url(base_url, anchor["href"])
            if predicate(url):
                candidates.append({"url": url, "text": anchor.get("text", "")})
        if not candidates:
            continue
        candidates.sort(key=lambda item: (title_is_bad(title_from_text(item["text"])), "vorschau" in item["text"].lower(), len(item["text"])))
        best = candidates[0]
        if best["url"] in seen:
            continue
        seen.add(best["url"])
        cards.append(
            {
                "url": best["url"],
                "anchor_text": best["text"],
                "context": html_to_text(block),
                "image_text": image_alt_text(block),
                "image_url": extract_first_image_url(block, base_url),
            }
        )
    return cards


def make_listing(source: str, city: City, card: dict[str, str], fallback_type: str = "any") -> Listing:
    combined = strip_vector_noise(clean_text(f"{card.get('anchor_text', '')} {card.get('image_text', '')} {card.get('context', '')}"))
    title = best_title(card.get("anchor_text", ""), card.get("image_text", ""), card.get("context", ""))
    listing_type = infer_listing_type(combined, fallback_type)
    rooms = parse_rooms(combined)
    if rooms and rooms > 8 and re.search(r"\b(studio|single\s*apartment|singleapartment|1[-\s]?(?:zi|zimmer))\b", title, flags=re.I):
        rooms = 1.0
    return Listing(
        source=source,
        title=title,
        url=card["url"],
        city_id=city.id,
        listing_type=listing_type,
        rent_eur=parse_price(combined),
        area_sqm=parse_area(combined),
        rooms=rooms,
        location=location_from_text(combined, city),
        image_url=card.get("image_url") or None,
        raw_text=combined[:1200],
    )


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "DNT": "1",
        },
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.6)
    raise last_error if last_error else RuntimeError("Request failed")


def selected_kinds(filters: dict) -> list[str]:
    kind = filters.get("propertyType", "any")
    if kind == "any":
        return ["apartment", "room", "house"]
    return [kind]


class RentalSource:
    key: str

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        raise NotImplementedError

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        raise NotImplementedError

    def search(self, city: City, filters: dict) -> SourceResult:
        listings: list[Listing] = []
        statuses: list[SourceStatus] = []
        urls = self.build_urls(city, filters)
        if not urls:
            return SourceResult([], [SourceStatus(self.key, True, "No search URL for the selected property type", 0)])
        for fallback_type, url in urls:
            try:
                html = fetch_html(url)
                parsed = self.parse(html, url, city, fallback_type)
                listings.extend(parsed)
                statuses.append(SourceStatus(self.key, True, f"Fetched {len(parsed)} listings", len(parsed), url))
            except Exception as exc:  # Network and remote HTML errors should not break the whole app.
                statuses.append(SourceStatus(self.key, False, f"{type(exc).__name__}: {exc}", 0, url))
            time.sleep(0.35)
        return SourceResult(dedupe_listings(listings)[:MAX_LISTINGS_PER_SOURCE], statuses)


class KleinanzeigenSource(RentalSource):
    key = "kleinanzeigen"

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        paths = {
            "apartment": ("wohnung-mieten", "c203"),
            "room": ("auf-zeit-wg", "c199"),
            "house": ("haus-mieten", "c205"),
        }
        urls = []
        for kind in selected_kinds(filters):
            slug, category = paths[kind]
            urls.append((kind, f"https://www.kleinanzeigen.de/s-{slug}/{city.kleinanzeigen_slug}/{category}{city.kleinanzeigen_location}"))
        return urls

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        cards = collect_listing_cards_from_blocks(
            html,
            base_url,
            r"<article\b(?=[^>]*\baditem\b)[\s\S]*?</article>",
            lambda url: "/s-anzeige/" in url,
        )
        if not cards:
            cards = collect_listing_anchors(html, base_url, lambda url: "/s-anzeige/" in url)
        return [make_listing(self.key, city, card, fallback_type) for card in cards]


class ImmoScoutSource(RentalSource):
    key = "immoscout"

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        paths = {
            "apartment": "wohnung-mieten",
            "room": "wg-zimmer",
            "house": "haus-mieten",
        }
        return [
            (kind, f"https://www.immobilienscout24.de/Suche/de/{city.immoscout_state}/{city.immoscout_city}/{paths[kind]}")
            for kind in selected_kinds(filters)
        ]

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        cards = collect_listing_anchors(html, base_url, lambda url: "/expose/" in url or "/neubau/" in url)
        return [make_listing(self.key, city, card, fallback_type) for card in cards]


class ImmoweltSource(RentalSource):
    key = "immowelt"

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        paths = {
            "apartment": "wohnungen/mieten",
            "house": "haeuser/mieten",
        }
        return [
            (kind, f"https://www.immowelt.de/suche/{city.immowelt_slug}/{paths[kind]}")
            for kind in selected_kinds(filters)
            if kind in paths
        ]

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        cards = collect_listing_anchors(html, base_url, lambda url: "/expose/" in url)
        return [make_listing(self.key, city, card, fallback_type) for card in cards]


class WGGesuchtSource(RentalSource):
    key = "wg_gesucht"

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        if city.wg_city_id is None:
            return []
        urls: list[tuple[str, str]] = []
        for kind in selected_kinds(filters):
            if kind == "room":
                urls.append((kind, f"https://www.wg-gesucht.de/wg-zimmer-in-{city.wg_slug}.{city.wg_city_id}.0.1.0.html"))
            elif kind == "apartment":
                urls.append((kind, f"https://www.wg-gesucht.de/1-zimmer-wohnungen-in-{city.wg_slug}.{city.wg_city_id}.1.1.0.html"))
                urls.append((kind, f"https://www.wg-gesucht.de/wohnungen-in-{city.wg_slug}.{city.wg_city_id}.2.1.0.html"))
        return urls

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        json_ld_listings = self.parse_json_ld(html, base_url, city, fallback_type)
        if json_ld_listings:
            return json_ld_listings

        def is_listing(url: str) -> bool:
            return "wg-gesucht.de" in url and re.search(r"(?:/|\.)([0-9]+)\.html(?:$|[?#])", url) is not None

        cards = collect_listing_anchors(html, base_url, is_listing)
        return [make_listing(self.key, city, card, fallback_type) for card in cards]

    def parse_json_ld(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        listings: list[Listing] = []
        for match in re.finditer(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html, flags=re.I | re.S):
            raw = unescape(match.group(1)).strip().rstrip(";")
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    payload = json.JSONDecoder().raw_decode(raw)[0]
                except json.JSONDecodeError:
                    continue
            for item in self._walk_json_ld_items(payload):
                url = item.get("url")
                name = item.get("name")
                if not url or not name:
                    continue
                offer = item.get("offers") if isinstance(item.get("offers"), dict) else {}
                address = {}
                main_entity = item.get("mainEntity")
                if isinstance(main_entity, dict):
                    maybe_address = main_entity.get("address")
                    if isinstance(maybe_address, dict):
                        address = maybe_address
                location = clean_text(
                    " ".join(
                        str(address.get(key, "") or "")
                        for key in ["postalCode", "addressRegion", "addressLocality"]
                    )
                ) or city.name
                context = clean_text(
                    " ".join(
                        str(part or "")
                        for part in [
                            name,
                            item.get("description"),
                            offer.get("price"),
                            location,
                        ]
                    )
                )
                rent = parse_price(f"{offer.get('price', '')} €") if offer.get("price") else None
                listings.append(
                    Listing(
                        source=self.key,
                        title=best_title(str(name)),
                        url=absolute_url(base_url, str(url)),
                        city_id=city.id,
                        listing_type=infer_listing_type(context, fallback_type),
                        rent_eur=rent,
                        area_sqm=parse_area(context),
                        rooms=parse_rooms(context),
                        location=location,
                        image_url=normalize_image_url(base_url, str(item.get("image", "") or "")),
                        raw_text=context[:1200],
                    )
                )
        return dedupe_listings(listings)

    def _walk_json_ld_items(self, payload: object) -> list[dict]:
        found: list[dict] = []
        if isinstance(payload, list):
            for item in payload:
                found.extend(self._walk_json_ld_items(item))
        elif isinstance(payload, dict):
            if payload.get("@type") == "RealEstateListing":
                found.append(payload)
            main_entity = payload.get("mainEntity")
            if isinstance(main_entity, dict):
                found.extend(self._walk_json_ld_items(main_entity))
            item_list = payload.get("itemListElement")
            if isinstance(item_list, list):
                for list_item in item_list:
                    if isinstance(list_item, dict):
                        found.extend(self._walk_json_ld_items(list_item.get("item")))
        return found


class HousingAnywhereSource(RentalSource):
    key = "housinganywhere"

    def build_urls(self, city: City, filters: dict) -> list[tuple[str, str]]:
        return [("any", f"https://housinganywhere.com/s/{city.housinganywhere_slug}")]

    def parse(self, html: str, base_url: str, city: City, fallback_type: str) -> list[Listing]:
        def is_listing(url: str) -> bool:
            return "housinganywhere.com" in url and any(token in url for token in ["/room/", "/rooms/", "/listing/", "/rentals/"])

        cards = collect_listing_anchors(html, base_url, is_listing)
        if not cards:
            parser = AnchorCollector()
            parser.feed(html)
            cards = [
                {"url": absolute_url(base_url, anchor["href"]), "anchor_text": anchor["text"], "context": anchor["text"]}
                for anchor in parser.anchors
                if "€" in anchor.get("text", "") and len(anchor.get("text", "")) > 20
            ]
        return [make_listing(self.key, city, card, fallback_type) for card in cards]


SOURCES: dict[str, RentalSource] = {
    "kleinanzeigen": KleinanzeigenSource(),
    "immoscout": ImmoScoutSource(),
    "immowelt": ImmoweltSource(),
    "wg_gesucht": WGGesuchtSource(),
    "housinganywhere": HousingAnywhereSource(),
}


def dedupe_listings(listings: list[Listing]) -> list[Listing]:
    seen: set[str] = set()
    unique: list[Listing] = []
    for listing in listings:
        if listing.url in seen:
            continue
        seen.add(listing.url)
        unique.append(listing)
    return unique


def listing_matches_filters(listing: Listing | dict, filters: dict) -> bool:
    getter = listing.get if isinstance(listing, dict) else lambda key, default=None: getattr(listing, key, default)
    requested_type = filters.get("propertyType", "any")
    listing_type = getter("listing_type", "any")
    if requested_type != "any" and listing_type not in {requested_type, "any"}:
        return False

    max_rent = filters.get("maxRent")
    rent = getter("rent_eur")
    if max_rent not in (None, "", 0) and rent is not None and rent > int(max_rent):
        return False

    min_rooms = filters.get("minRooms")
    rooms = getter("rooms")
    if min_rooms not in (None, "", 0) and rooms is not None and rooms < float(min_rooms):
        return False

    min_area = filters.get("minArea")
    area = getter("area_sqm")
    if min_area not in (None, "", 0) and area is not None and area < float(min_area):
        return False

    keyword = clean_text(str(filters.get("keyword", ""))).lower()
    if keyword:
        haystack = clean_text(
            " ".join(
                str(getter(key, "") or "")
                for key in ["title", "location", "raw_text", "source", "listing_type"]
            )
        ).lower()
        if keyword not in haystack:
            return False
    return True
