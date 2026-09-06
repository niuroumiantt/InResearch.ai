"""One machine declaration for shared data rules; no duplicated threshold defaults."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'framework/data_contract.json'
CONTRACT = json.loads(PATH.read_text(encoding='utf-8'))
FRESH_DAYS = CONTRACT['fresh_days']
PRICE_FRESH = CONTRACT['price_fresh_days']
SOURCE_GRADES = set(CONTRACT['source_grades'])
STATUS_LEVELS = set(CONTRACT['project_statuses'])


def price_series_freq(record):
    explicit = record.get('frequency')
    if explicit in PRICE_FRESH:
        return explicit
    series = record.get('series_id', '')
    for rule in CONTRACT['price_frequency_rules']:
        if (rule.get('contains') and rule['contains'] in series) or any(series.startswith(p) for p in rule.get('prefixes', [])):
            return rule['frequency']
    return 'default'


def price_series_limit(record):
    return PRICE_FRESH[price_series_freq(record)]
