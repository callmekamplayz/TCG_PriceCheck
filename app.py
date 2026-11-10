import os, sqlite3, uuid, re
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus, urlparse, parse_qs
import streamlit as st
from st_keyup import st_keyup
import qrcode
from PIL import Image
import cv2
import numpy as np
import requests
import pandas as pd

DB="tcg_pricecheck.db"
st.set_page_config(page_title="TCG PriceCheck", page_icon="🃏", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.stApp{background:radial-gradient(ellipse at 15% 0%,#252d68 0%,#111831 48%,#090d1d 100%);color:#f5f6ff}
html,body,[class*="css"]{font-family:Inter,sans-serif}
.block-container{max-width:1150px;padding-top:1.5rem}
[data-testid="stHeader"]{background:transparent}
.hero{background:linear-gradient(120deg,#342c75aa,#18234fbb);border:1px solid #716bd055;border-radius:24px;padding:25px 28px;margin-bottom:20px}
.brand{font-size:2.2rem;font-weight:800;letter-spacing:-1px}.brand span{color:#ad9cff}
.tagline,.muted{color:#bfc7e8}
.panel{background:#151d3bea;border:1px solid #7e89c044;border-radius:20px;padding:20px;margin:10px 0;box-shadow:0 12px 35px #0003}
.metric{background:linear-gradient(135deg,#5744a955,#292d65);border:1px solid #9b8aff55;border-radius:16px;padding:18px}
.metric-label{color:#c3c8e5;font-size:.85rem}.metric-value{font-size:2.1rem;font-weight:800;color:white}
div.stButton>button,div.stDownloadButton>button{background:linear-gradient(110deg,#795cff,#5945db);color:white;border:0;border-radius:12px;font-weight:700;min-height:2.8rem;width:100%}
.stTextInput input,.stNumberInput input,.stSelectbox div[data-baseweb="select"]{background:#111831!important;color:#fff!important;border-radius:10px}
[data-testid="stTabs"] button{color:#cbd0ed;font-weight:700}
[data-testid="stTabs"] button[aria-selected="true"]{color:#b5a7ff}
hr{border-color:#8d97c033}
</style>
""", unsafe_allow_html=True)

def conn():
    c=sqlite3.connect(DB,check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY,name TEXT,game TEXT,set_name TEXT,
    number TEXT,condition TEXT,language TEXT,price REAL,currency TEXT,created TEXT)""")
    cols = [row[1] for row in c.execute("PRAGMA table_info(cards)")]
    if "image_url" not in cols:
        c.execute("ALTER TABLE cards ADD COLUMN image_url TEXT DEFAULT ''")
    if "catalog_id" not in cols:
        c.execute("ALTER TABLE cards ADD COLUMN catalog_id TEXT DEFAULT ''")
    c.execute("""CREATE TABLE IF NOT EXISTS price_snapshots (
        catalog_id TEXT NOT NULL, variant TEXT NOT NULL, day TEXT NOT NULL,
        source TEXT NOT NULL, currency TEXT NOT NULL, value REAL NOT NULL,
        PRIMARY KEY(catalog_id, variant, day, source))""")
    c.commit()
    return c

def get_card(cid):
    c=conn(); r=c.execute("SELECT id,name,game,set_name,number,condition,language,price,currency,created,image_url,catalog_id FROM cards WHERE id=?",(cid,)).fetchone(); c.close()
    if not r:return None
    return dict(zip(["id","name","game","set_name","number","condition","language","price","currency","created","image_url","catalog_id"],r))

def cards():
    c=conn(); rows=c.execute("SELECT id,name,game,set_name,number,condition,language,price,currency,created,image_url,catalog_id FROM cards ORDER BY created DESC").fetchall(); c.close()
    keys=["id","name","game","set_name","number","condition","language","price","currency","created","image_url","catalog_id"]
    return [dict(zip(keys,r)) for r in rows]

def qr(payload):
    q=qrcode.QRCode(box_size=9,border=3);q.add_data(payload);q.make(fit=True)
    b=BytesIO();q.make_image(fill_color="#10152f",back_color="white").save(b,format="PNG");return b.getvalue()

def decode(upload):
    im=Image.open(upload).convert("RGB")
    arr=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)
    value,_,_=cv2.QRCodeDetector().detectAndDecode(arr)
    return value.strip() if value else ""

def target(cid):
    root=os.getenv("TCG_APP_URL","https://tcg-pricecheck.streamlit.app").rstrip("/")
    return f"{root}/?listing={cid}" if root else f"?listing={cid}"

def ebay_url(card):
    q=" ".join(x for x in [card["name"],card["set_name"],card["number"],card["language"],card["condition"]] if x)
    return "https://www.ebay.co.uk/sch/i.html?_nkw="+quote_plus(q)+"&LH_Sold=1&LH_Complete=1"

def show(card):
    a,b=st.columns([1,1.35],gap="large")
    with a:
        st.markdown('<div class="panel">',unsafe_allow_html=True)
        if card.get("image_url"):
            card_image(card["image_url"], card["game"], width=230)
        st.caption("CARD LISTING")
        st.subheader(card["name"])
        st.write(" · ".join(x for x in [card["game"],card["set_name"],card["number"]] if x))
        st.markdown(f'<div class="metric"><div class="metric-label">Seller asking price</div><div class="metric-value">{card["currency"]}{card["price"]:.2f}</div></div>',unsafe_allow_html=True)
        st.write(f'**Condition:** {card["condition"]}')
        st.write(f'**Language:** {card["language"]}')
        st.markdown('</div>',unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel">',unsafe_allow_html=True)
        st.subheader("Recent eBay sales")
        st.caption("Compare completed sales for the same printing, language and condition.")
        st.link_button("Search completed eBay UK sales ↗",ebay_url(card))
        st.info("Automatic display of the three latest sold prices will be enabled when your eBay API access and the relevant endpoint are confirmed. No sample prices are presented as real sales.")
        st.markdown('</div>',unsafe_allow_html=True)
    if card.get("catalog_id"):
        with st.expander("📈 Card prices and available history", expanded=False):
            price_panel(card["catalog_id"], card["game"], card["name"], card.get("set_name", ""), card.get("number", ""))

# API results are cached to avoid excessive requests to community databases.
HEADERS = {"User-Agent": "TCGPriceCheckStudentProject/1.1 (Streamlit educational card catalogue)", "Accept": "application/json"}


def api_json(url, **kwargs):
    response = requests.get(url, headers=HEADERS, timeout=15, **kwargs)
    if response.status_code == 404:
        return {}  # Some card databases use 404 for an empty search.
    response.raise_for_status()
    return response.json()


def parse_card_query(query):
    """Separate a trailing collector/set number from a card name.

    Examples: 'Gengar ex 35', 'Gengar ex #035', 'Jinx OGN-025/298'.
    """
    query = " ".join(query.strip().split())
    match = re.match(r"^(.+?)\s+#?((?:[A-Za-z]{2,8}-)?[A-Za-z]?\d+[A-Za-z]?(?:/\d+)?)$", query)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return query, ""


def number_matches(actual, wanted):
    """Match collector numbers with/without leading zeroes, including set codes."""
    if not wanted:
        return True
    actual, wanted = str(actual or "").strip().upper(), str(wanted or "").strip().lstrip("#").upper()
    if actual == wanted:
        return True
    # Avoid treating a short number as a random substring (35 should not match 135).
    def numeric_part(value):
        head = value.split("/", 1)[0].split("-")[-1]
        return str(int(head)) if head.isdigit() else head.lstrip("0")
    if not wanted or not actual:
        return False
    if "-" in wanted:
        return actual.startswith(wanted) or actual == wanted
    if numeric_part(actual) == numeric_part(wanted):
        return True
    # Yu-Gi-Oh! sets are printed as e.g. LOB-035; preserve all leading zeros.
    return False


def rank_and_filter(results, number):
    """Apply the collector-number filter before showing the 24-card grid."""
    if number:
        results = [item for item in results if number_matches(item.get("number", ""), number)]
    return results[:24]


@st.cache_data(ttl=3600, show_spinner=False)
def search_pokemon(query):
    name, number = parse_card_query(query)
    # TCGdex filters name and localId independently; this allows name + number.
    params = {"name": name, "pagination:page": 1, "pagination:itemsPerPage": 100 if number else 24}
    if number and re.fullmatch(r"\d+", number):
        params["localId"] = number
    items = api_json("https://api.tcgdex.net/v2/en/cards", params=params)
    results = []
    for item in (items if isinstance(items, list) else []):
        image = item.get("image") or ""
        results.append({"id": "pokemon:" + str(item.get("id", "")),
                        "name": item.get("name", ""), "set_name": "",
                        "number": item.get("localId", ""),
                        "image_url": f"{image}/high.webp" if image else ""})
    return rank_and_filter(results, number)


@st.cache_data(ttl=3600, show_spinner=False)
def pokemon_details(card_id):
    return api_json(f"https://api.tcgdex.net/v2/en/cards/{card_id}")


@st.cache_data(ttl=3600, show_spinner=False)
def search_yugioh(query):
    name, number = parse_card_query(query)
    data = api_json("https://db.ygoprodeck.com/api/v7/cardinfo.php", params={"fname": name})
    results = []
    for card in data.get("data", []):
        sets = card.get("card_sets") or [{}]
        images = card.get("card_images") or []
        artwork = images[0].get("image_url", "") if images else ""
        for edition in sets:
            set_code = edition.get("set_code", "")
            if number and not number_matches(set_code, number):
                continue
            results.append({"id": f"yugioh:{card['id']}:{set_code}",
                            "name": card.get("name", ""),
                            "set_name": edition.get("set_name", ""),
                            "number": set_code, "image_url": artwork})
            if len(results) >= 24:
                return results
    return results


@st.cache_data(ttl=3600, show_spinner=False)
def search_magic(query):
    name, number = parse_card_query(query)
    search = f'{name} game:paper'
    if number:
        search += f' cn:{number}'  # Scryfall collector-number operator.
    data = api_json("https://api.scryfall.com/cards/search",
                    params={"q": search, "unique": "prints", "order": "name"})
    results = []
    for card in data.get("data", []):
        faces = card.get("card_faces") or []
        image = (card.get("image_uris") or (faces[0].get("image_uris", {}) if faces else {})).get("normal", "")
        results.append({"id": "magic:" + str(card.get("id", "")),
                        "name": card.get("name", ""), "set_name": card.get("set_name", ""),
                        "number": card.get("collector_number", ""), "image_url": image})
    return rank_and_filter(results, number)


@st.cache_data(ttl=3600, show_spinner=False)
def search_riftbound(query):
    """RiftHunt search has a documented data[] response and images.normal URLs."""
    name, number = parse_card_query(query)
    # Searching just the name ensures RiftHunt won't treat the number as another word.
    data = api_json("https://api.rifthunt.com/cards/search",
                    params={"q": name, "unique": "prints"})
    entries = data.get("data", []) if isinstance(data, dict) else []
    results = []
    for card in entries:
        if not isinstance(card, dict):
            continue
        images = card.get("images") or {}
        image = images.get("normal") or images.get("large") or images.get("small") or ""
        results.append({"id": "riftbound:" + str(card.get("printing_id") or card.get("id")),
                        "name": card.get("name", ""),
                        "set_name": card.get("set_name") or card.get("set") or "",
                        "number": card.get("collector_number", ""),
                        "image_url": image})
    return rank_and_filter(results, number)


SEARCHERS = {"Pokémon": search_pokemon, "Yu-Gi-Oh!": search_yugioh,
             "Magic: The Gathering": search_magic, "Riftbound": search_riftbound}


@st.cache_data(ttl=86400, show_spinner=False)
def cached_yugioh_image(url):
    """YGOPRODeck prohibits repeated direct hotlinking; fetch and cache in the app."""
    if not url.startswith("https://images.ygoprodeck.com/images/cards/"):
        return None
    response = requests.get(url, headers=HEADERS, timeout=12)
    response.raise_for_status()
    return response.content


def card_image(url, game, width=None):
    if not url:
        st.caption("Image unavailable — you can enter details manually.")
        return
    try:
        if game == "Yu-Gi-Oh!":
            value = cached_yugioh_image(url)
            st.image(value, width=width, use_container_width=width is None)
        else:
            st.image(url, width=width, use_container_width=width is None)
    except Exception:
        st.caption("Image temporarily unavailable")

# Official catalogue IDs are saved with each listing so another set/printing cannot
# accidentally be presented as the price history for the selected card.
@st.cache_data(ttl=21600, show_spinner=False)
def market_observations(catalog_id, game):
    if game == "Pokémon" and catalog_id.startswith("pokemon:"):
        obj = pokemon_details(catalog_id.split(":", 1)[1]); pricing = obj.get("pricing") or {}
        provider = pricing.get("tcgplayer") or {}  # Only show verified provider entries if available
        quotes = []
        for finish, row in provider.items():
            if isinstance(row, dict) and isinstance(row.get("marketPrice"), (int, float)):
                quotes.append(("TCGplayer via TCGdex", "USD", str(finish), float(row["marketPrice"])))
        return quotes, ""
    if game == "Magic: The Gathering" and catalog_id.startswith("magic:"):
        obj = api_json("https://api.scryfall.com/cards/" + quote(catalog_id.split(":", 1)[1]))
        prices = obj.get("prices") or {}
        quote_map = [("usd", "Non-foil", "USD"), ("usd_foil", "Foil", "USD"),
                     ("usd_etched", "Etched", "USD")]
        quotes = [("Scryfall indicative", curr, variant, float(prices[k]))
                  for k, variant, curr in quote_map if prices.get(k) not in (None, "")]
        return quotes, (obj.get("purchase_uris") or {}).get("tcgplayer", "")
    if game == "Yu-Gi-Oh!" and catalog_id.startswith("yugioh:"):
        # The set-specific API price is NOT the overall TCGplayer price for a card name.
        code = catalog_id.split(":", 2)[2]
        if not code:
            return [], ""
        obj = api_json("https://db.ygoprodeck.com/api/v7/cardsetsinfo.php", params={"setcode": code})
        rows = obj if isinstance(obj, list) else (obj.get("data", [obj]) if isinstance(obj, dict) else [])
        for item in rows:
            if str(item.get("set_code", "")).upper() == code.upper():
                try:
                    return [("YGOPRODeck set estimate", "USD", "Set edition", float(item["set_price"]))], ""
                except (ValueError, KeyError, TypeError):
                    pass
        return [], ""
    return [], ""

@st.cache_data(ttl=3600, show_spinner=False)
def riftbound_market(catalog_id):
    """Return current TCGplayer prices for one RiftHunt printing, not just a card name."""
    printing_id = catalog_id.split(":", 1)[1]
    details = api_json("https://api.rifthunt.com/cards/" + quote(printing_id))
    prices = details.get("prices") or {}
    observations = []
    for finish in details.get("finishes") or []:
        row = prices.get(finish) or {}
        amount = row.get("market") if isinstance(row, dict) else None
        if isinstance(amount, (float, int)):
            observations.append(("TCGplayer via RiftHunt", "USD", finish.title(), float(amount)))
    return observations, (details.get("purchase_uris") or {}).get("tcgplayer", "")


@st.cache_data(ttl=3600, show_spinner=False)
def yugioh_tcgplayer_general(catalog_id):
    """YGOPRODeck reports a card-wide TCGplayer quote, not a set-specific price."""
    card_id = catalog_id.split(":", 2)[1]
    data = api_json("https://db.ygoprodeck.com/api/v7/cardinfo.php", params={"id": card_id})
    items = data.get("data") or []
    if not items:
        return []
    quotes = items[0].get("card_prices") or []
    try:
        price = float(quotes[0]["tcgplayer_price"])
    except (IndexError, TypeError, ValueError, KeyError):
        return []
    return [("TCGplayer via YGOPRODeck (all printings; not set-specific)", "USD", "Card-wide estimate", price)]


@st.cache_data(ttl=21600, show_spinner=False)
def riftbound_history(catalog_id):
    uuid = catalog_id.split(":", 1)[1]
    details = api_json("https://api.rifthunt.com/cards/" + quote(uuid))
    rid = details.get("riftbound_id")
    if not rid:
        return {}, ""
    params = {"range": "3m"}
    if details.get("collector_number"):
        params["collector"] = details["collector_number"]
    if details.get("slug"):
        params["slug"] = details["slug"]
    history = api_json("https://api.rifthunt.com/prices/" + quote(rid, safe="") + "/history", params=params)
    return history, (details.get("purchase_uris") or {}).get("tcgplayer", "")


def record_price_snapshots(catalog_id, observations):
    # One genuine provider observation per date, printing and finish.
    day = datetime.now(timezone.utc).date().isoformat()
    c = conn()
    try:
        for source, currency, variant, amount in observations:
            if amount >= 0:
                c.execute("""INSERT OR REPLACE INTO price_snapshots
                    (catalog_id, variant, day, source, currency, value)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (catalog_id, variant, day, source, currency, amount))
        c.commit()
    finally:
        c.close()


def snapshot_data(catalog_id):
    c = conn()
    try:
        return c.execute("""SELECT day, variant, source, currency, value FROM price_snapshots
                            WHERE catalog_id=? ORDER BY day""", (catalog_id,)).fetchall()
    finally:
        c.close()


def price_panel(catalog_id, game, name, set_name, number):
    st.caption(f"Exact printing: {name} · {set_name} · #{number}")
    search = quote_plus(" ".join(filter(None, [name, set_name, str(number)])))
    tcg_search_url = "https://www.tcgplayer.com/search/all/product?q=" + search
    st.link_button("🛒 Find this card on TCGplayer", tcg_search_url)
    st.caption("Verify the exact set, number, finish and condition on TCGplayer before comparing prices. A search link is not a verified product match.")
    try:
        if game == "Riftbound" and catalog_id.startswith("riftbound:"):
            live_prices, live_link = riftbound_market(catalog_id)
            if live_prices:
                st.markdown("**Current TCGplayer market prices (USD) — exact printing**")
                for source, currency, finish, amount in live_prices:
                    st.write(f"{finish}: **${amount:.2f}** — {source}")
            else:
                st.caption("No current TCGplayer quote for this printing.")
            history, purchase = riftbound_history(catalog_id)
            purchase = live_link or purchase
            dates = history.get("dates") or []
            # Keep different markets/currencies separate: USD vs EUR are not comparable.
            series = history.get("series") or {}
            for source, title in (("tcgplayer", "TCGplayer market price (USD)"),
                                  ("cardmarket", "Cardmarket trend (EUR)")):
                data = series.get(source) or {}
                plots = {}
                for finish in ("normal", "foil"):
                    values = data.get(finish) or []
                    if len(values) == len(dates):
                        plots[finish.capitalize()] = pd.to_numeric(pd.Series(values), errors="coerce")
                if plots:
                    # Construct directly from lists to avoid index alignment inserting NaN.
                    df = pd.DataFrame({k: v.to_numpy() for k, v in plots.items()}, index=pd.to_datetime(dates))
                    df = df.dropna(how="all")
                    if not df.empty:
                        st.markdown(f"**{title}**")
                        st.line_chart(df)
            if not dates or not series or not any((series.get(src) or {}).get(f) for src in series for f in ("normal","foil")):
                st.info("No historical Riftbound prices have been recorded for this exact printing yet.")
            st.caption("RiftHunt tracks individual Riftbound printings. Its price history begins 9 Nov 2026; missing dates are not estimated.")
            st.link_button("View exact printing on TCGplayer" if purchase else "Search TCGplayer for this card",
                           purchase or tcg_search_url)
            return
        observations, purchase = market_observations(catalog_id, game)
        if game == "Yu-Gi-Oh!" and catalog_id.startswith("yugioh:"):
            try:
                observations = observations + yugioh_tcgplayer_general(catalog_id)
            except requests.RequestException:
                pass
        if observations:
            record_price_snapshots(catalog_id, observations)
            st.markdown("**Latest available market estimates**")
            for source, currency, finish, amount in observations:
                sign = {"USD":"$", "EUR":"€", "GBP":"£"}.get(currency, currency + " ")
                st.write(f"{finish}: **{sign}{amount:.2f}** — {source}")
            rows = snapshot_data(catalog_id)
            # Charts only after at least two distinct observation dates (never fake history).
            if len({r[0] for r in rows}) >= 2:
                for currency in sorted(set(r[3] for r in rows)):
                    filtered = [r for r in rows if r[3] == currency]
                    chart = pd.DataFrame(filtered, columns=["date", "finish", "source", "currency", "price"])
                    chart["date"] = pd.to_datetime(chart["date"])
                    wide = chart.pivot_table(index="date", columns="finish", values="price", aggfunc="last")
                    if len(wide) >= 2:
                        st.markdown(f"**Recorded price history ({currency})**")
                        st.line_chart(wide)
            else:
                st.info("Price tracking has started. A chart will appear after prices are recorded on at least two different days.")
            st.caption("Sources differ: Yu-Gi-Oh! TCGplayer quote is card-wide, not printing-specific. Other estimates are labelled by provider. Price snapshots are gathered only while the card is viewed and may be lost on Streamlit Community Cloud.")
        else:
            st.info("No exact-printing market price available from the free catalogue API. Check the marketplace listing instead.")
        st.link_button("View exact printing on TCGplayer" if purchase else "Search TCGplayer for this card",
                       purchase or tcg_search_url)
    except (requests.RequestException, ValueError, KeyError, TypeError, pd.errors.ParserError):
        st.warning("The price provider is unavailable right now. You can still compare marketplace listings.")
        st.link_button("Search TCGplayer for this card", tcg_search_url)

st.markdown('<div class="hero"><div class="brand">🃏 TCG <span>PriceCheck</span></div><div class="tagline">Scan · Compare · Buy with confidence</div></div>',unsafe_allow_html=True)

listing=st.query_params.get("listing","")
if listing:
    c=get_card(listing)
    if c:
        st.success("Listing opened from QR code");show(c);st.divider()

t1,t2,t3=st.tabs(["✚  Create listing","▦  Scan QR code","▤  My listings"])
with t1:
    st.markdown('<div class="panel">',unsafe_allow_html=True)
    st.subheader("Create a new listing")
    st.caption("Search by name or name + card number (e.g. Gengar ex 35), then choose the correct printing.")
    game=st.selectbox("Trading card game",["Pokémon","Yu-Gi-Oh!","Magic: The Gathering","Riftbound","Other"])
    selected_key = "selected_card"
    if game in SEARCHERS:
        query=st_keyup(f"Search {game} cards", placeholder="e.g. Gengar ex 35, Dark Magician, Jinx OGN-025", key=f"search_{game}", debounce=500)
        if len(query.strip()) >= 2:
            try:
                results = SEARCHERS[game](query.strip())
                if not results:
                    st.info("No matching cards found. Try the card name without its number, or enter the details manually.")
                else:
                    st.caption(f"Showing up to {len(results)} matching cards. Select the correct artwork and printing.")
                    if game == "Riftbound" and not any(item.get("image_url") for item in results):
                        st.info("Riftbound returned cards without images. You can still select a card or enter details manually.")
                    for offset in range(0, len(results), 4):
                        cols=st.columns(4)
                        for card_index, (col,item) in enumerate(zip(cols,results[offset:offset+4]), start=offset):
                            with col:
                                card_image(item.get("image_url", ""), game)
                                st.caption(f"{item['name']} · {item.get('set_name','')} · #{item.get('number','')}")
                                if st.button("Select card", key=f"select_{game}_{card_index}"):
                                    choice = dict(item, game=game)
                                    if game == "Pokémon":
                                        try:
                                            details=pokemon_details(item["id"].split(":", 1)[1])
                                            image=details.get("image") or ""
                                            choice.update(name=details.get("name", item["name"]),
                                                          set_name=(details.get("set") or {}).get("name", ""),
                                                          number=details.get("localId", item["number"]),
                                                          image_url=f"{image}/high.webp" if image else item["image_url"])
                                        except requests.RequestException:
                                            st.warning("Could not load extra details; using the search result.")
                                    st.session_state[selected_key]=choice
                                    st.rerun()
            except requests.RequestException as e:
                st.warning(f"Card search is unavailable right now ({e}). You can enter the details manually.")
    selected=st.session_state.get(selected_key)
    if selected and selected.get("game") != game:
        selected = None
    if selected:
        st.success(f"Selected: {selected['name']} — {selected.get('set_name','')} #{selected.get('number','')}")
        card_image(selected.get("image_url", ""), game, width=210)
        with st.expander("📈 Price check and available history", expanded=True):
            price_panel(selected["id"], game, selected["name"],
                        selected.get("set_name", ""), selected.get("number", ""))
        if st.button("Clear selected card"):
            st.session_state.pop(selected_key,None)
            st.rerun()
    with st.form("new"):
        left,right=st.columns(2)
        with left:
            name=st.text_input("Card name",value=selected["name"] if selected else "",placeholder="e.g. Charizard ex")
            set_name=st.text_input("Set / expansion",value=selected["set_name"] if selected else "")
            number=st.text_input("Card number",value=selected["number"] if selected else "")
        with right:
            condition=st.selectbox("Condition",["Near Mint","Lightly Played","Moderately Played","Heavily Played","Damaged"])
            language=st.selectbox("Language",["English","Japanese","Other"])
            currency=st.selectbox("Currency",["£","$","€"])
            price=st.number_input("Asking price",min_value=.01,value=10.0,step=.5)
        submit=st.form_submit_button("▦  Generate QR code")
    if submit:
        if not name.strip():st.error("Enter a card name.")
        else:
            card={"id":uuid.uuid4().hex[:12],"name":name.strip(),"game":game,"set_name":set_name.strip(),
            "number":number.strip(),"condition":condition,"language":language,"price":price,"currency":currency,
            "created":datetime.now(timezone.utc).isoformat(),"image_url":selected.get("image_url","") if selected else "",
            "catalog_id": selected.get("id", "") if selected else ""}
            c=conn();c.execute("INSERT INTO cards (id,name,game,set_name,number,condition,language,price,currency,created,image_url,catalog_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",tuple(card.values()));c.commit();c.close()
            st.session_state["created_card"]=card
    card=st.session_state.get("created_card")
    if card:
        st.success("Listing created.");show(card)
        png=qr(target(card["id"]));st.image(png,width=190,caption="Your listing QR code")
        st.download_button("Download QR code (PNG)",png,file_name=f'tcg-{card["id"]}.png',mime="image/png")
    st.markdown('</div>',unsafe_allow_html=True)

with t2:
    st.markdown('<div class="panel">',unsafe_allow_html=True)
    st.subheader("Scan a QR code")
    st.caption("Take a photo or upload an existing QR image.")
    camera=st.camera_input("Use camera")
    upload=st.file_uploader("Or upload QR image",type=["png","jpg","jpeg"])
    source=camera if camera is not None else upload
    if source:
        try:
            value=decode(source)
            if not value:st.error("No QR code found. Try a clearer, straight-on image.")
            else:
                cid=parse_qs(urlparse(value).query).get("listing",[""])[0] if "listing=" in value else (value if "://" not in value else "")
                card=get_card(cid) if cid else None
                if card:st.success("Card listing found");show(card)
                else:st.error("This QR code does not match a saved listing in this app.")
        except Exception as e:st.error(f"Could not read QR image: {e}")
    st.markdown('</div>',unsafe_allow_html=True)

with t3:
    st.markdown('<div class="panel">',unsafe_allow_html=True)
    st.subheader("My listings")
    saved=cards()
    if not saved:st.caption("No listings yet. Create your first listing.")
    for card in saved:
        with st.expander(f'{card["name"]} — {card["currency"]}{card["price"]:.2f}'):
            show(card)
            st.download_button("Download QR code",qr(target(card["id"])),file_name=f'tcg-{card["id"]}.png',mime="image/png",key=card["id"])
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<p class="muted" style="text-align:center">TCG PriceCheck · Student innovation prototype · eBay sales integration pending API configuration</p>',unsafe_allow_html=True)
