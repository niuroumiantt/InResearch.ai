"""Native power quantities. A range has no implicit representative scalar."""
import copy
import math
import re

UNITS = {'MW': 1, 'GW': 1000}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def check(value):
    if value is None or number(value):
        return value
    if not isinstance(value, dict) or set(value) - {'value', 'value_range', 'unit', 'assumptions', 'basis'}:
        raise ValueError('site_observation_capacity_value')
    if value.get('unit') not in UNITS or ('value' in value) == ('value_range' in value):
        raise ValueError('site_quantity_unit_or_value')
    assumptions = value.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not isinstance(s, str) or not s.strip() for s in assumptions):
        raise ValueError('site_quantity_assumptions')
    if 'basis' in value and (not isinstance(value['basis'], str) or not value['basis'].strip()):
        raise ValueError('site_quantity_basis')
    if 'value_range' in value:
        pair = value['value_range']
        if not isinstance(pair, list) or len(pair) != 2 or not all(number(v) for v in pair) or pair[0] > pair[1]:
            raise ValueError('site_quantity_range')
        if not assumptions and not (isinstance(value.get('basis'), str) and value['basis'].strip()):
            raise ValueError('site_quantity_range_basis_required')
    elif not number(value['value']):
        raise ValueError('site_observation_capacity_value')
    components = value['value_range'] if 'value_range' in value else [value['value']]
    if not all(math.isfinite(n * UNITS[value['unit']]) for n in components):
        raise ValueError('site_quantity_conversion_overflow')
    return value


def bounds_mw(value):
    check(value)
    if value is None:
        return None, None
    if number(value):
        return value, value
    factor = UNITS[value['unit']]
    pair = value['value_range'] if 'value_range' in value else [value['value']] * 2
    converted = tuple(v * factor for v in pair)
    if not all(math.isfinite(v) for v in converted):
        raise ValueError('site_quantity_conversion_overflow')
    return converted


def scalar_mw(value):
    check(value)
    # Even equal endpoints remain an explicitly ranged source assertion.
    if isinstance(value, dict) and 'value_range' in value:
        return None
    return bounds_mw(value)[0]


def canonical(value):
    low, high = bounds_mw(value)
    return {'range_mw': [low, high]} if isinstance(value, dict) and 'value_range' in value else {'value_mw': low}


def literal_ranges_mw(text):
    """Only explicitly connected bounds share a trailing power unit."""
    unit = r'(MW|GW|megawatts?|gigawatts?|兆瓦|吉瓦)'
    pattern = r'(?<![\w.\-])(\d[\d,]*(?:\.\d+)?)\s*' + unit + r'?\s*(?:to|through|至|到|[-–—~])\s*(\d[\d,]*(?:\.\d+)?)\s*' + unit + r'(?![A-Za-z/\-])(?!\s+hours?\b)'
    def factor(raw):
        return 1000 if raw.lower().startswith('g') or raw == '吉瓦' else 1
    result = []
    for lo, first_unit, hi, last_unit in re.findall(pattern, text, re.I):
        pair = (float(lo.replace(',', '')) * factor(first_unit or last_unit), float(hi.replace(',', '')) * factor(last_unit))
        if pair[0] <= pair[1]:
            result.append(pair)
    return result


def project_fields(fields):
    """Scalar-compatible projection plus the complete native quantity map."""
    result = copy.deepcopy(fields)
    quantities = {}
    for key in ('capacity_it_mw', 'capacity_facility_mw', 'capacity_planned_it_mw'):
        if key in result:
            quantities[key] = copy.deepcopy(result[key])
            result[key] = scalar_mw(result[key])
    if 'capacity_it_mw_by_status' in result:
        parts = result['capacity_it_mw_by_status'] or {}
        quantities['capacity_it_mw_by_status'] = copy.deepcopy(parts)
        scalars = {k: scalar_mw(v) for k, v in parts.items()}
        result['capacity_it_mw_by_status'] = {} if any(v is None for v in scalars.values()) else scalars
    return result, quantities
