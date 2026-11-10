import os, sqlite3, uuid
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, parse_qs
import streamlit as st
import qrcode
from PIL import Image
import cv2
import numpy as np

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
    c.commit()
    return c

def get_card(cid):
    c=conn(); r=c.execute("SELECT * FROM cards WHERE id=?",(cid,)).fetchone(); c.close()
    if not r:return None
    return dict(zip(["id","name","game","set_name","number","condition","language","price","currency","created"],r))

def cards():
    c=conn(); rows=c.execute("SELECT * FROM cards ORDER BY created DESC").fetchall(); c.close()
    keys=["id","name","game","set_name","number","condition","language","price","currency","created"]
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
    root=os.getenv("TCG_APP_URL","").rstrip("/")
    return f"{root}/?listing={cid}" if root else f"?listing={cid}"

def ebay_url(card):
    q=" ".join(x for x in [card["name"],card["set_name"],card["number"],card["language"],card["condition"]] if x)
    return "https://www.ebay.co.uk/sch/i.html?_nkw="+quote_plus(q)+"&LH_Sold=1&LH_Complete=1"

def show(card):
    a,b=st.columns([1,1.35],gap="large")
    with a:
        st.markdown('<div class="panel">',unsafe_allow_html=True)
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
    st.caption("Enter the card details and asking price to generate a unique QR code.")
    with st.form("new"):
        left,right=st.columns(2)
        with left:
            name=st.text_input("Card name",placeholder="e.g. Charizard ex")
            game=st.selectbox("Trading card game",["Pokémon","Yu-Gi-Oh!","Magic: The Gathering","Other"])
            set_name=st.text_input("Set / expansion")
            number=st.text_input("Card number")
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
            "created":datetime.now(timezone.utc).isoformat()}
            c=conn();c.execute("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?)",tuple(card.values()));c.commit();c.close()
            st.session_state["created_card"]=card
    card=st.session_state.get("created_card")
    if card:
        st.success("Listing created.");show(card)
        png=qr(target(card["id"]));st.image(png,width=190,caption="Your listing QR code")
        st.download_button("Download QR code (PNG)",png,file_name=f'tcg-{card["id"]}.png',mime="image/png")
        if not os.getenv("TCG_APP_URL"):
            st.warning("To let other phones open this QR code, deploy the app publicly and set TCG_APP_URL to its HTTPS address.")
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
