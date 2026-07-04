from __future__ import annotations

import re

KNOWN_AIRPORT_ALIASES: dict[str, list[str]] = {
    "bengaluru": ["BLR"],
    "bangalore": ["BLR"],
    "delhi": ["DEL"],
    "new delhi": ["DEL"],
    "mumbai": ["BOM"],
    "goa": ["GOX", "GOI"],
    "north goa": ["GOX", "GOI"],
    "south goa": ["GOI", "GOX"],
    "darjeeling": ["IXB"],
    "bagdogra": ["IXB"],
    "kolkata": ["CCU"],
    "chennai": ["MAA"],
    "hyderabad": ["HYD"],
    "mysuru": ["MYQ"],
    "mysore": ["MYQ"],
    "kochi": ["COK"],
    "cochin": ["COK"],
    "jaipur": ["JAI"],
    "ahmedabad": ["AMD"],
    "pune": ["PNQ"],
    "srinagar": ["SXR"],
    "leh": ["IXL"],
    "dehradun": ["DED"],
    "rishikesh": ["DED"],
    "varanasi": ["VNS"],
    "udaipur": ["UDR"],
    "amritsar": ["ATQ"],
}


def normalize_location_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def resolve_known_airports(value: str) -> list[str]:
    normalized = normalize_location_key(value)
    if not normalized:
        return []
    if normalized in KNOWN_AIRPORT_ALIASES:
        return KNOWN_AIRPORT_ALIASES[normalized]
    if re.fullmatch(r"[A-Za-z]{3}", value.strip()):
        return [value.strip().upper()]
    for alias, airports in KNOWN_AIRPORT_ALIASES.items():
        if normalized in alias or alias in normalized:
            return airports
    return []
