import os, sqlite3, uuid
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, parse_qs
import streamlit as st
import qrcode
from PIL import Image
import cv2
import numpy as np
import requests

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
    c.commit()
    return c

def get_card(cid):
    c=conn(); r=c.execute("SELECT id,name,game,set_name,number,condition,language,price,currency,created,image_url FROM cards WHERE id=?",(cid,)).fetchone(); c.close()
    if not r:return None
    return dict(zip(["id","name","game","set_name","number","condition","language","price","currency","created","image_url"],r))

def cards():
    c=conn(); rows=c.execute("SELECT id,name,game,set_name,number,condition,language,price,currency,created,image_url FROM cards ORDER BY created DESC").fetchall(); c.close()
    keys=["id","name","game","set_name","number","condition","language","price","currency","created","image_url"]
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

# API results are cached to avoid excessive requests to community databases.
HEADERS = {"User-Agent": "TCGPriceCheckStudentProject/1.1 (Streamlit educational card catalogue)", "Accept": "application/json"}


def api_json(url, **kwargs):
    response = requests.get(url, headers=HEADERS, timeout=15, **kwargs)
    if response.status_code == 404:
        return {}  # Some card databases use 404 for an empty search.
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def search_pokemon(name):
    items = api_json("https://api.tcgdex.net/v2/en/cards", params={
        "name": name, "pagination:page": 1, "pagination:itemsPerPage": 24})
    results = []
    for item in (items if isinstance(items, list) else []):
        image = item.get("image") or ""
        results.append({"id": "pokemon:" + str(item.get("id", "")),
                        "name": item.get("name", ""), "set_name": "",
                        "number": item.get("localId", ""),
                        "image_url": f"{image}/high.webp" if image else ""})
    return results


@st.cache_data(ttl=3600, show_spinner=False)
def pokemon_details(card_id):
    return api_json(f"https://api.tcgdex.net/v2/en/cards/{card_id}")


@st.cache_data(ttl=3600, show_spinner=False)
def search_yugioh(name):
    data = api_json("https://db.ygoprodeck.com/api/v7/cardinfo.php", params={"fname": name})
    results = []
    for card in data.get("data", []):
        # A Yu-Gi-Oh! name can be printed in many expansions; show distinct sets.
        sets = card.get("card_sets") or [{}]
        images = card.get("card_images") or []
        artwork = images[0].get("image_url", "") if images else ""
        for edition in sets[:12]:
            results.append({"id": f"yugioh:{card['id']}:{edition.get('set_code','')}",
                            "name": card.get("name", ""),
                            "set_name": edition.get("set_name", ""),
                            "number": edition.get("set_code", ""),
                            "image_url": artwork})
            if len(results) >= 24:
                return results
    return results


@st.cache_data(ttl=3600, show_spinner=False)
def search_magic(name):
    # unique=prints permits choosing a specific collector number and expansion.
    data = api_json("https://api.scryfall.com/cards/search",
                    params={"q": f'{name} game:paper', "unique": "prints", "order": "name"})
    results = []
    for card in data.get("data", [])[:24]:
        faces = card.get("card_faces") or []
        image = (card.get("image_uris") or (faces[0].get("image_uris", {}) if faces else {})).get("normal", "")
        results.append({"id": "magic:" + str(card.get("id", "")),
                        "name": card.get("name", ""), "set_name": card.get("set_name", ""),
                        "number": card.get("collector_number", ""), "image_url": image})
    return results


def _rift_image(printing):
    """OpenRift provides imageId + /media/cards/{imageId}-400w.webp."""
    images = printing.get("images") or []
    if isinstance(images, dict):
        images = list(images.values())
    first = images[0] if images else {}
    image_id = (first.get("imageId") if isinstance(first, dict) else None) or printing.get("imageId")
    if image_id:
        return f"https://openrift.app/media/cards/{image_id}-400w.webp"
    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def search_riftbound(name):
    data = api_json("https://openrift.app/api/v1/search", params={"q": name, "limit": 24})
    # Search API may wrap results in a data object with a cards/items array.
    payload = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = next((payload[k] for k in ("cards", "results", "items", "hits")
                        if isinstance(payload.get(k), list)), [])
    else:
        entries = []
    results = []
    for row in entries[:24]:
        if not isinstance(row, dict):
            continue
        card = row.get("card") if isinstance(row.get("card"), dict) else row
        printing = row.get("printing") if isinstance(row.get("printing"), dict) else row
        if printing is row and isinstance(card.get("printings"), list) and card["printings"]:
            printing = card["printings"][0]
        set_data = printing.get("set") or row.get("set") or {}
        if isinstance(set_data, dict):
            set_name = set_data.get("name", "")
        else:
            set_name = str(set_data)
        results.append({"id": "riftbound:" + str(printing.get("id") or card.get("id") or len(results)),
                        "name": card.get("name") or row.get("name") or "Unknown card",
                        "set_name": set_name,
                        "number": printing.get("publicCode") or printing.get("collectorNumber")
                                  or card.get("publicCode") or "",
                        "image_url": _rift_image(printing)})
    return results


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
    st.caption("Search for a card, choose the correct printing, or type the details manually.")
    game=st.selectbox("Trading card game",["Pokémon","Yu-Gi-Oh!","Magic: The Gathering","Riftbound","Other"])
    selected_key = "selected_card"
    if game in SEARCHERS:
        query=st.text_input(f"Search {game} cards", placeholder="e.g. Charizard, Blue-Eyes, Lightning Bolt or Jinx", key=f"search_{game}")
        if len(query.strip()) >= 2:
            try:
                results = SEARCHERS[game](query.strip())
                if not results:
                    st.info("No matching cards found. You can enter the details manually.")
                else:
                    st.caption(f"Showing up to {len(results)} matching cards. Select the correct artwork and printing.")
                    for offset in range(0, len(results), 4):
                        cols=st.columns(4)
                        for col,item in zip(cols,results[offset:offset+4]):
                            with col:
                                card_image(item.get("image_url", ""), game)
                                st.caption(f"{item['name']} · {item.get('set_name','')} · #{item.get('number','')}")
                                if st.button("Select card", key=f"select_{game}_{item['id']}_{offset}"):
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
            "created":datetime.now(timezone.utc).isoformat(),"image_url":selected.get("image_url","") if selected else ""}
            c=conn();c.execute("INSERT INTO cards (id,name,game,set_name,number,condition,language,price,currency,created,image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",tuple(card.values()));c.commit();c.close()
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
