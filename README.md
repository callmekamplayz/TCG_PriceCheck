# TCG PriceCheck — styled Python prototype

## Run locally
1. Install Python 3.10 or newer.
2. In this folder run: `python -m pip install -r requirements.txt`
3. Start: `streamlit run app.py`

## Public QR codes
To make QR codes open on other phones, deploy the app to a public HTTPS address and set `TCG_APP_URL` to that address before starting Streamlit.
Windows PowerShell: `$env:TCG_APP_URL="https://your-app.streamlit.app"`
macOS/Linux: `export TCG_APP_URL="https://your-app.streamlit.app"`

## Included
- Dark navy/purple responsive interface inspired by the visual concept.
- Create listings with card details and seller asking price.
- Generate/download QR codes; scan via camera or uploaded image.
- Save listings in SQLite.
- Search eBay UK completed/sold listings.

## eBay API
The sold-sales panel is ready to be connected, but the exact eBay endpoint and response schema must be confirmed against the API access you receive. The app does not fabricate sold prices.
