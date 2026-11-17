"""Scheduled daily TickerMint snapshot collector; run with GitHub Actions.

Errors for individual products are logged without preventing other cards from being saved.
"""
import sys
import time
import requests
from free_history import fetch_prices
from history_store import configured, tracked_products, save_history
from extra_sources import current_catalog_prices


def run(max_products=60, delay_seconds=1):
    if not configured():
        raise RuntimeError('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY as GitHub Actions secrets')
    products = tracked_products(limit=max_products)
    errors, saved = 0, 0
    for product in products:
        pid = product['product_id']
        try:
            if str(pid).startswith('catalog:'):
                history = current_catalog_prices(product['catalog_id'], product['game'])
                source = ('Scryfall indicative' if product['game'] == 'Magic: The Gathering' else
                          'TCGplayer via RiftHunt' if product['game'] == 'Riftbound' else
                          'YGOPRODeck set estimate')
                count = save_history(pid, history, source=source)
            else:
                history = fetch_prices(pid)
                count = save_history(pid, history)
            saved += count
            print(f'{pid}: {count} dated price records stored')
        except (requests.RequestException, ValueError, KeyError) as e:
            errors += 1
            print(f'{pid}: failed: {type(e).__name__}: {e}', file=sys.stderr)
        time.sleep(delay_seconds)
    print(f'{len(products)} products checked; {saved} observations upserted; {errors} failed')
    if errors and errors == len(products):
        raise RuntimeError('All price collection requests failed')


if __name__ == '__main__':
    run()
