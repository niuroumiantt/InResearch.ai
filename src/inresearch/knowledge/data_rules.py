"""One machine declaration for shared data rules; no duplicated threshold defaults."""

from inresearch.paths import project_root
import json
import math

PATH = project_root() / 'framework/data_contract.json'
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


def price_errors(record):
    """The same price contract at validation and every mutation boundary."""
    errors = []
    if record.get('grade') == 'estimate' and not record.get('assumptions'):
        errors.append('estimate 级必须写 assumptions（推导链条）')
    if record.get('grade') not in SOURCE_GRADES:
        errors.append('grade 非法')
    value = record.get('value')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        errors.append('value 必须是数字')
    return errors
