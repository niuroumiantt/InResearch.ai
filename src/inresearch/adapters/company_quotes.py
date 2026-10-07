"""Small Nasdaq quote cache. No filings, article bodies, credentials or arbitrary URLs.

Quotes refresh in a bounded background pool, so a slow market provider never
blocks the company profile. Exchange timestamps are preserved verbatim.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
import re
import threading
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import write_json

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='company-quotes')
GUARD = threading.Lock()
PENDING = set()
ATTEMPTS = {}
TTL = 600
PUBLIC_FIELDS = ('symbol', 'price', 'currency', 'market_cap', 'change', 'change_percent', 'as_of',
                 'market_status', 'provider', 'source_url', 'retrieved_at', 'retrieved_epoch', 'delay_note')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r'[$+\-\d,.% ]+', value):
        return None
    try:
        n = float(value.replace('$', '').replace(',', '').replace('%', '').strip())
        return n if math.isfinite(n) else None
    except ValueError:
        return None


def read_provider(symbol, kind):
    url = f'https://api.nasdaq.com/api/quote/{symbol}/{kind}?assetclass=stocks'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
                                'Referer': 'https://www.nasdaq.com/'})
    with build_opener(NoRedirect()).open(req, timeout=6) as r:
        body = r.read(262145)
    if len(body) > 262144:
        raise ValueError('quote_response_too_large')
    return json.loads(body)['data']


def normalize(symbol, info, summary):
    if not isinstance(info, dict) or not isinstance(info.get('symbol'), str) or info['symbol'].upper() != symbol:
        raise ValueError('quote_symbol_mismatch')
    if summary and (not isinstance(summary, dict) or not isinstance(summary.get('symbol', symbol), str) or summary.get('symbol', symbol).upper() != symbol):
        raise ValueError('quote_summary_symbol_mismatch')
    primary = info.get('primaryData') or {}
    if not isinstance(primary, dict): raise ValueError('invalid_quote_data')
    price = number(primary.get('lastSalePrice'))
    stamp = primary.get('lastTradeTimestamp')
    if price is None or price <= 0 or not isinstance(stamp, str) or not stamp.strip() or len(stamp) > 120:
        raise ValueError('quote_missing_price_or_time')
    summary_data = (summary or {}).get('summaryData') or {}
    cap_data = summary_data.get('MarketCap') if isinstance(summary_data, dict) else None
    cap = number(cap_data.get('value')) if isinstance(cap_data, dict) else None
    return {'symbol': symbol, 'price': price, 'currency': 'USD', 'market_cap': cap if cap and cap > 0 else None,
            'change': number(primary.get('netChange')), 'change_percent': number(primary.get('percentageChange')),
            'as_of': stamp, 'market_status': str(info.get('marketStatus') or '')[:60],
            'provider': 'Nasdaq', 'source_url': f'https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'retrieved_epoch': time.time(),
            'delay_note': '按提供方时间展示；不保证实时行情'}


def refresh(path, key, symbol):
    try:
        info = read_provider(symbol, 'info')
        try:
            summary = read_provider(symbol, 'summary')
        except (OSError, ValueError, KeyError, TypeError):
            summary = None
        value = normalize(symbol, info, summary)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, value)
    except (OSError, ValueError, KeyError, TypeError):
        pass  # Existing cache remains intact; next projection reports unavailable/stale.
    finally:
        with GUARD:
            PENDING.discard(key)


def snapshot(root, company):
    ticker = company.get('ticker') or ''
    if not re.fullmatch(r'(NASDAQ|NYSE):[A-Z][A-Z0-9.\-]{0,14}', ticker):
        return {'status': 'unsupported' if ticker else 'unregistered', 'ticker': ticker}
    symbol = ticker.split(':', 1)[1]
    path = workspace_path('data/raw/company-quotes/'+company['company_id']+'.json', root)
    key = str(path)
    try:
        value = json.loads(path.read_text())
        if (not isinstance(value, dict) or value.get('symbol') != symbol
                or type(value.get('retrieved_epoch')) not in (int, float)
                or not math.isfinite(value['retrieved_epoch']) or value['retrieved_epoch'] > time.time()+60
                or type(value.get('price')) not in (int, float) or not math.isfinite(value['price']) or value['price'] <= 0
                or not isinstance(value.get('as_of'), str) or not value['as_of'].strip()):
            raise ValueError('invalid_quote_cache')
        value = {k: value[k] for k in PUBLIC_FIELDS if k in value}
        for field in ('market_cap', 'change', 'change_percent'):
            number_value = value.get(field)
            if type(number_value) not in (int, float) or not math.isfinite(number_value):
                value[field] = None
        value['currency'] = 'USD'
        value['provider'] = 'Nasdaq'
        value['source_url'] = f'https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}'
    except (OSError, ValueError, TypeError):
        value = None
    age = time.time()-value['retrieved_epoch'] if value else math.inf
    if os.environ.get('INRESEARCH_MARKET_ENABLED', '1') != '0' and age >= TTL:
        with GUARD:
            if key not in PENDING and len(PENDING) < 8 and time.time()-ATTEMPTS.get(key, 0) > 60:
                ATTEMPTS[key] = time.time()
                PENDING.add(key)
                POOL.submit(refresh, path, key, symbol)
    with GUARD:
        pending = key in PENDING
    return {**(value or {}), 'ticker': ticker, 'status': ('stale' if age >= TTL else 'cached') if value
            else ('pending' if pending else 'unavailable'), 'refreshing': pending}
