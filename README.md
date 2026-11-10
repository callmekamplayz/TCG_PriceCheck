# TCG PriceCheck — Free Historical Price Charts

This edition keeps the card search, QR generation, listings, and black/purple Streamlit theme. Its new **free_history.py** module integrates TickerMint's *no-key*, free-for-non-commercial-use historical TCGplayer market prices for **Pokémon, Yu-Gi-Oh! and Riftbound**.

## What the free integration can and cannot do

- **Pokémon / Yu-Gi-Oh! / Riftbound:** Searches TickerMint by card name and number, then strictly checks the card **name, set and collector number**. If multiple printings match, the user chooses the edition / finish. Real dated market prices are displayed with the existing GBP / USD / EUR and 1M / 3M / 6M / 1Y controls. An explicit `Prices: TickerMint` link credits the provider.
- **No API key:** TickerMint currently documents **approximately 30 days** of data (and a per-IP request limit), not full 1Y history. The range buttons do not create missing prices. Cached lookups help conserve the free quota. The provider's terms restrict free access to non-commercial/personal uses.
- **Riftbound fallback:** If no verified TickerMint match exists, the prior RiftHunt market/history code still runs; RiftHunt's history starts 9 Nov 2026.
- **Magic: The Gathering:** Current Scryfall prices and locally tracked snapshots are retained. MTGJSON offers up to 90 days of genuine price data, but the public AllPrices download is tens/hundreds of megabytes and is impractical to fetch on every Streamlit interaction; it has **not** been connected. A preprocessed/cache-backed MTGJSON integration would be separate work.
- **Sales bars:** No sales-volume bars are displayed because these APIs don't provide a comparable daily sold-count series for the selected printing. Invented data is never used.
- **Currencies:** Historical prices are in USD. The existing historical Frankfurter conversion is applied for GBP/EUR when available. If the FX service is down, choose USD.
- **Online storage:** Local SQLite listings are **not durable on Streamlit Community Cloud** after redeployment or restart.

## How to update your existing GitHub website

1. Extract this ZIP.
2. Upload **app.py**, **free_history.py** and **requirements.txt** to the **root** of your existing TCG_PriceCheck repository; replace the existing app.py and requirements.txt. **Do not delete the repository.**
3. Commit changes. Streamlit Community Cloud will deploy the modified app.
4. Open https://tcg-pricecheck.streamlit.app/, choose a card, and expand the price history panel.
5. Try a specific printing such as **M Gengar EX — Phantom Forces #35**. Choose a TickerMint product if several printings match.

The free TickerMint endpoint can enforce a per-IP quota; users of a public Streamlit deployment may share an IP and encounter rate limiting. If the provider is unavailable, the existing current-price sources remain usable.

### Testing

Locally verified: `python -m py_compile app.py free_history.py`; offline mocked HTTP searches, exact-printing checks, rejection of wrong sets/numbers, market history response parsing, and date/period logic. **Live TickerMint or Streamlit deployment was not testable in this environment**; the documented endpoints and response formats were used. Be cautious if the external API changes.

References: https://tickermint.cards/developers/python and https://tickermint.cards/developers; https://rifthunt.com/api/; https://www.mtgjson.com/downloads/all-files/
