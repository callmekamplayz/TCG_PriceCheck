# TCG PriceCheck — multi-game card search

Create card listings for **Pokémon, Yu-Gi-Oh!, Magic: The Gathering, Riftbound**, or **Other**, with a search-and-select image picker. Set/expansion, collector number, and card name are pre-filled where available. You can always enter details manually.

## Deploying the updated version

1. Upload `app.py`, `requirements.txt`, and this `README.md` to the **root** of your existing GitHub repository, replacing the older versions.
2. Streamlit Community Cloud normally redeploys when it detects the GitHub commit.
3. Open https://tcg-pricecheck.streamlit.app/ and try searching `Pikachu`, `Dark Magician`, `Lightning Bolt`, or `Jinx` in Create listing.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

QR codes default to https://tcg-pricecheck.streamlit.app/ . Override with the `TCG_APP_URL` environment variable for another deployment.

## Search providers

- Pokémon — [TCGdex](https://tcgdex.dev/)
- Yu-Gi-Oh! — [YGOPRODeck](https://ygoprodeck.com/api-guide/). Images are fetched once by the app server and cached to avoid repeatedly hotlinking the image CDN.
- Magic: The Gathering — [Scryfall](https://scryfall.com/docs/api)
- Riftbound — [OpenRift](https://openrift.app/developers). This is a newer community-maintained interface; image/printing results may vary. Riftbound images are owned by Riot Games; consult Riot's fan-content policies before public or commercial use.

Search services require an internet connection and may occasionally be unavailable. Image availability and coverage vary. Manual entry is retained.

## Known limitations

- SQLite data stored on Streamlit Community Cloud is **not persistent across restarts/redeploys**, and isn't shared across local vs cloud installs. Use hosted storage for durable QR-linked listings.
- The eBay sold-price panel links to a search; automatic recent sold prices aren't implemented.
- Selecting a Yu-Gi-Oh! set uses the primary artwork supplied by the provider; verify alternate art manually.
- Only the first 24 results are shown in each search. Narrow the search for more precision.
