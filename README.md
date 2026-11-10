# TCG PriceCheck — single interactive price chart

## What's changed

- **One chart per selected card**, instead of separate TCGplayer and Cardmarket plots.
- **Currency picker:** GBP (£), USD ($), EUR (€). The underlying data retains its original currency. Conversions use actual daily historical exchange rates from Frankfurter, including previous business-day rates for weekends/holidays; if unavailable, the app says so rather than guessing.
- **Range buttons:** 1M, 3M, 6M, 1Y. Riftbound's data is requested from RiftHunt for the selected range; locally observed price snapshots are filtered by the selected range.
- Normal/foil remain separate **lines within the same chart**; an interactive legend and tooltips help comparison.
- **Honest missing-history handling:** One observed date is shown as a point with an explanation. No artificial prices or drawn trend lines are generated for dates without data.
- Chart controls have distinct keys when different listings are visible simultaneously.

## Important limitations

RiftHunt's Riftbound historical TCGplayer data begins **9 November 2026**, so a 1Y setting will *not* produce a year's chart. Other games have only app-recorded observation dates, **not** a TCGplayer 1-year history. These snapshots are saved in local SQLite; on Streamlit Community Cloud, they can disappear on restart. A hosted database and authorised historical pricing data source would be needed for persistent historical charts covering all games.

Historical currency conversion changes the displayed currency, not the marketplace or price source. Cardmarket EUR prices are not combined with TCGplayer USD prices.

## Deploy to your existing site

1. Download/extract the package.
2. Replace `app.py` and `requirements.txt` in the root of your **existing** GitHub repository (no need to delete it).
3. Commit, then reopen https://tcg-pricecheck.streamlit.app/ after Streamlit redeploys.

Requires Streamlit 1.45+ for segmented range controls. Live provider requests need to be verified on your deployed site; Python syntax and chart-record parsing were checked locally.
