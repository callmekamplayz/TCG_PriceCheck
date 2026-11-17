"""Persistent exact-printing observations on Supabase (REST/PostgREST).

This module deliberately does not expose database credentials to browser clients.
Only a trusted Streamlit process or scheduled GitHub workflow should import it.
"""
import os
from datetime import datetime, timezone
import requests
import pandas as pd


def configured():
    return bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_ROLE_KEY'))


def _request(method, table, *, params=None, payload=None):
    if not configured():
        raise RuntimeError('Supabase credentials not configured')
    url = os.environ['SUPABASE_URL'].rstrip('/') + '/rest/v1/' + table
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    headers = {'apikey': key,
               'Content-Type': 'application/json', 'Accept': 'application/json'}
    # Supabase's sb_secret_ keys are API keys, not JWT bearer tokens.
    # Legacy service_role JWTs still need the Authorization header.
    if not key.startswith('sb_secret_'):
        headers['Authorization'] = 'Bearer ' + key
    if method == 'POST':
        headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
    resp = requests.request(method, url, headers=headers, params=params, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json() if resp.content else []


def watch_printing(game, catalog_id, product_id, name, set_name, card_number, printing=''):
    """Track a VERIFIED TickerMint product, not a fuzzy title query."""
    pid = str(product_id)
    if not pid.isdecimal():
        raise ValueError('Invalid TickerMint product ID')
    row = dict(product_id=pid, game=str(game)[:50], catalog_id=str(catalog_id)[:150],
               name=str(name)[:200], set_name=str(set_name)[:200],
               card_number=str(card_number)[:80], printing=str(printing)[:120])
    _request('POST', 'tracked_products', params={'on_conflict': 'product_id'}, payload=[row])


def save_history(product_id, frame, source='TickerMint TCGplayer market'):
    """Upsert genuine dated prices, preserving date+finish+provider uniqueness."""
    pid = str(product_id)
    rows = []
    for item in frame.to_dict('records'):
        date = pd.to_datetime(item.get('date'), errors='coerce', utc=True)
        price = pd.to_numeric(item.get('price'), errors='coerce')
        if pd.isna(date) or pd.isna(price) or float(price) <= 0:
            continue
        rows.append({'product_id': pid, 'day': date.date().isoformat(),
                     'finish': str(item.get('finish') or 'Unknown')[:100],
                     'source': source, 'currency': str(item.get('source_currency') or 'USD'),
                     'price': float(price)})
    # daily API replies can duplicate entries; choose the latest per key
    unique = {(row['product_id'],row['day'],row['finish'],row['source']): row for row in rows}
    values = list(unique.values())
    for i in range(0, len(values), 200):
        _request('POST', 'price_history',
                 params={'on_conflict': 'product_id,day,finish,source'},
                 payload=values[i:i+200])
    return len(values)


def read_history(product_id, limit=10000):
    rows = _request('GET', 'price_history', params={
        'select': 'day,finish,currency,price', 'product_id': 'eq.'+str(product_id),
        'order': 'day.asc', 'limit': str(limit)})
    if not rows:
        return pd.DataFrame(columns=['date','price','finish','source_currency'])
    data = pd.DataFrame(rows)
    return data.rename(columns={'day':'date','currency':'source_currency'})[
        ['date','price','finish','source_currency']].assign(date=lambda x: pd.to_datetime(x.date))


def tracked_products(limit=100):
    # limit prevents runaway API usage on the free upstream service
    return _request('GET', 'tracked_products', params={
        'select': 'product_id,game,catalog_id,name,set_name,card_number,printing',
        'order': 'created_at.asc', 'limit': str(limit)})


def watch_catalog(game, catalog_id, name, set_name, card_number):
    """Register a catalogue ID for daily price checks when TickerMint is unavailable."""
    _request('POST', 'tracked_products', params={'on_conflict':'product_id'},
             payload=[dict(product_id='catalog:'+str(catalog_id), game=str(game),
                           catalog_id=str(catalog_id), name=str(name)[:200],
                           set_name=str(set_name)[:200], card_number=str(card_number)[:80],
                           printing='')])
