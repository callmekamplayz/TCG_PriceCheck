"""Free current-price observations for catalogues without long history feeds."""
from datetime import datetime, timezone
import requests
import pandas as pd


def current_catalog_prices(catalog_id, game, session=None):
    get = (session or requests).get
    observations = []
    if game == 'Magic: The Gathering' and catalog_id.startswith('magic:'):
        uid = catalog_id.split(':',1)[1]
        r = get('https://api.scryfall.com/cards/' + uid, timeout=20,
                headers={'User-Agent':'TCGPriceCheck/1.0', 'Accept':'application/json'})
        r.raise_for_status()
        obj = r.json()
        for k, finish in [('usd','Non-foil'),('usd_foil','Foil'),('usd_etched','Etched')]:
            try:
                p = float((obj.get('prices') or {}).get(k))
                if p>0: observations.append((finish,p))
            except (TypeError,ValueError):
                continue
    elif game == 'Riftbound' and catalog_id.startswith('riftbound:'):
        uid = catalog_id.split(':',1)[1]
        r = get('https://api.rifthunt.com/cards/' + uid, timeout=20)
        r.raise_for_status()
        obj = r.json()
        for finish in obj.get('finishes') or []:
            try:
                p = float(((obj.get('prices') or {}).get(finish) or {}).get('market'))
                if p>0: observations.append((str(finish).title(),p))
            except (TypeError, ValueError):
                continue
    elif game == 'Yu-Gi-Oh!' and catalog_id.startswith('yugioh:'):
        parts = catalog_id.split(':',2)
        if len(parts)==3:
            r = get('https://db.ygoprodeck.com/api/v7/cardsetsinfo.php',
                    params={'setcode':parts[2]}, timeout=20)
            r.raise_for_status()
            obj = r.json()
            rows = obj if isinstance(obj,list) else (obj.get('data') or [obj])
            for row in rows:
                if row.get('set_code','').upper()==parts[2].upper():
                    try:
                        p=float(row['set_price'])
                        if p>0: observations.append(('Set edition',p))
                    except (ValueError,TypeError,KeyError):
                        pass
                    break
    today = datetime.now(timezone.utc).date().isoformat()
    return pd.DataFrame([{'date':today,'price':amount,'finish':finish,
                          'source_currency':'USD'} for finish,amount in observations],
                        columns=['date','price','finish','source_currency'])
