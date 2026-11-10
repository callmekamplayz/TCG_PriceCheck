"""Free, non-commercial TickerMint market history for exact card printings.

TickerMint: https://tickermint.cards/developers
The unauthenticated endpoint currently documents a 30-day window; the free quota
and access rules may change. Never present unverified printings as a match.
"""
import re
import requests
import pandas as pd

BASE = "https://api.tickermint.cards"
GAMES = {"Pokémon": "pokemon", "Yu-Gi-Oh!": "yugioh", "Riftbound": "riftbound"}


def clean(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def normalized_number(value):
    """35, 035/119 and #035 should compare equally, but not 135."""
    text = str(value or "").strip().lower().lstrip("#").split("/", 1)[0]
    # Prefer exact set+number for alphanumeric identifiers such as OGN-025.
    parts = re.match(r"^([a-z]+[- ])?(\d+)([a-z]*)$", text)
    if parts:
        return (parts.group(1) or "").strip(" -"), str(int(parts.group(2))), parts.group(3)
    return ("", text, "")


def number_equal(expected, actual):
    if not expected or not actual:
        return False
    exp, got = normalized_number(expected), normalized_number(actual)
    if exp == got:
        return True
    # Allow a provider to give OGN-025 when user has just 25, not vice versa.
    return not exp[0] and exp[1:] == got[1:]


def name_tokens(s):
    words = clean(s).split()
    return set(w for w in words if w not in {"the", "of", "and", "card", "alternate", "art", "secret"})


def printing_matches(hit, name, set_name, number):
    """Conservative match: card name, set and number must agree.
    Never silently select another edition when multiple products share a name.
    """
    if not isinstance(hit, dict) or not hit.get("product_id"):
        return False
    if not number_equal(number, hit.get("card_number", hit.get("number"))):
        return False
    want_name, got_name = name_tokens(name), name_tokens(hit.get("name"))
    if not want_name or not got_name:
        return False
    # Allow API suffixes e.g. '(Holofoil)' but require meaningful name overlap.
    common = len(want_name & got_name)
    if common / len(want_name) < 0.7 or common / len(got_name) < 0.45:
        return False
    want_set = name_tokens(set_name)
    got_set = name_tokens(hit.get("set_name"))
    # Never match solely on card number/name across different known sets.
    if want_set and got_set and len(want_set & got_set) / len(want_set) < 0.6:
        return False
    return True


def find_printings(name, set_name, number, game, session=None):
    if game not in GAMES or not number:
        return []
    get = (session or requests).get
    # Search by name and collector number. API returns a bare array.
    params = {"q": " ".join([name, str(number)]), "game": GAMES[game]}
    response = get(f"{BASE}/products/search", params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    hits = data if isinstance(data, list) else (data.get("results") or data.get("data") or [])
    valid = [h for h in hits if printing_matches(h, name, set_name, number)]
    # Some queries search only exact text; retry name alone, if necessary.
    if not valid:
        response = get(f"{BASE}/products/search", params={"q": name, "game": GAMES[game]}, timeout=15)
        response.raise_for_status()
        obj = response.json()
        hits = obj if isinstance(obj, list) else (obj.get("results") or obj.get("data") or [])
        valid = [h for h in hits if printing_matches(h, name, set_name, number)]
    # Deduplicate products returned by overlapping queries.
    return list({str(h["product_id"]): h for h in valid}.values())[:12]


def parse_prices(payload):
    """TickerMint /products/{id}/prices documents {printing: [{snapshot_date, market}]}.
    Return stable, chart-ready columns; never invent daily data or sold volume.
    """
    rows = []
    if not isinstance(payload, dict):
        return pd.DataFrame(columns=["date", "price", "finish", "source_currency"])
    for finish, history in payload.items():
        if not isinstance(history, list):
            continue
        for value in history:
            if not isinstance(value, dict):
                continue
            date = pd.to_datetime(value.get("snapshot_date", value.get("date")), errors="coerce")
            try:
                price = float(value.get("market"))
            except (TypeError, ValueError):
                continue
            if pd.notna(date) and price > 0:
                rows.append({"date": date, "price": price,
                             "finish": str(finish), "source_currency": "USD"})
    return pd.DataFrame(rows, columns=["date", "price", "finish", "source_currency"])


def fetch_prices(product_id, session=None):
    pid = str(product_id)
    if not pid.isdecimal():
        raise ValueError("TickerMint product IDs must be numeric")
    r = (session or requests).get(f"{BASE}/products/{pid}/prices", timeout=15)
    r.raise_for_status()
    return parse_prices(r.json())
