"""Native site resource observations; power, energy and water stay distinct.

The canonical unit is a comparison unit, never a replacement for native values.
An interval has no representative scalar. Reporting periods and measurement
boundaries are part of the observation identity, not optional display labels.
"""
import copy
import math
import re

DEFINITIONS = {
    'electricity_consumption_mwh': {'label': '电耗', 'unit': 'MWh', 'dimension': 'energy',
        'units': {'kWh': .001, 'MWh': 1, 'GWh': 1000, 'TWh': 1000000}},
    'water_consumption_m3': {'label': '耗水量', 'unit': 'm³', 'dimension': 'volume',
        'units': {'L': .001, 'm3': 1, 'm³': 1, 'US gal': .003785411784}},
    'water_withdrawal_m3': {'label': '取水量', 'unit': 'm³', 'dimension': 'volume',
        'units': {'L': .001, 'm3': 1, 'm³': 1, 'US gal': .003785411784}},
    'water_use_m3_per_day': {'label': '日用水量', 'unit': 'm³/day', 'dimension': 'flow',
        'units': {'m3/day': 1, 'm³/day': 1, 'L/day': .001, 'US gal/day': .003785411784}},
    'pue': {'label': 'PUE', 'unit': 'PUE', 'dimension': 'ratio', 'units': {'PUE': 1}},
    'wue_l_per_kwh_it': {'label': 'WUE', 'unit': 'L/kWh IT', 'dimension': 'intensity',
        'units': {'L/kWh IT': 1, 'm3/MWh IT': 1, 'm³/MWh IT': 1}},
}
FIELDS = frozenset(DEFINITIONS)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def check(key, value):
    from . import observation_time
    definition = DEFINITIONS[key]
    if value is None:
        return value
    allowed = {'value', 'value_range', 'unit', 'basis', 'assumptions',
               'period_start', 'period_end', 'boundary', 'measurement_kind'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('resource_metric_native_quantity_required')
    if value.get('unit') not in definition['units'] or ('value' in value) == ('value_range' in value):
        raise ValueError('resource_metric_dimension_or_value')
    pair = value.get('value_range', [value.get('value')] * 2)
    if not isinstance(pair, list) or len(pair) != 2 or not all(number(n) for n in pair) or pair[0] > pair[1]:
        raise ValueError('resource_metric_invalid_range')
    if not all(math.isfinite(n * definition['units'][value['unit']]) for n in pair):
        raise ValueError('resource_metric_conversion_overflow')
    if key == 'pue' and pair[0] < 1:
        raise ValueError('resource_metric_pue_below_one')
    if not isinstance(value.get('boundary'), str) or not value['boundary'].strip():
        raise ValueError('resource_metric_boundary_required')
    if value.get('measurement_kind') not in ('measured', 'reported', 'estimated', 'design', 'forecast'):
        raise ValueError('resource_metric_measurement_kind_required')
    if not isinstance(value.get('basis'), str) or not value['basis'].strip():
        raise ValueError('resource_metric_basis_required')
    assumptions = value.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not isinstance(a, str) or not a.strip() for a in assumptions):
        raise ValueError('resource_metric_assumptions_invalid')
    if value['measurement_kind'] in ('estimated', 'forecast') and not assumptions:
        raise ValueError('resource_metric_estimate_assumptions_required')
    if 'period_start' not in value or 'period_end' not in value:
        raise ValueError('resource_metric_reporting_period_required')
    observation_time.validate_period(value['period_start'], value['period_end'])
    return value


def canonical(key, value):
    check(key, value)
    if value is None:
        return None
    factor = DEFINITIONS[key]['units'][value['unit']]
    pair = value.get('value_range', [value.get('value')] * 2)
    return {'range': [n * factor for n in pair], 'ranged': 'value_range' in value,
            'period_start': value['period_start'], 'period_end': value['period_end'],
            'boundary': value['boundary'], 'measurement_kind': value['measurement_kind']}


def literal_bounds(key, quote):
    """Require the connected native unit; MWh is never interpreted as MW."""
    units = DEFINITIONS[key]['units']
    unit = '(' + '|'.join(re.escape(u) for u in sorted(units, key=len, reverse=True)) + ')'
    num = r'(\d[\d,]*(?:\.\d+)?)'
    end = r'(?![A-Za-z0-9/³])'
    result = []
    for lo, first, hi, last in re.findall(num + r'\s*' + unit + r'?\s*(?:to|至|到|[-–—~])\s*' + num + r'\s*' + unit + end, quote):
        result.append(([float(lo.replace(',', '')) * units[first or last],
                        float(hi.replace(',', '')) * units[last]], True))
    for n, u in re.findall(num + r'\s*' + unit + end, quote):
        v = float(n.replace(',', '')) * units[u]
        result.append(([v, v], False))
    return result


def supported(key, native, quote):
    """Literal support is a mechanical prerequisite; C3 checks period and scope."""
    expected = canonical(key, native)
    if expected is None:
        return True
    for pair, ranged in literal_bounds(key, quote):
        if ranged != expected['ranged']:
            continue
        if all(abs(a-b) <= 1e-9 * max(1, abs(a), abs(b)) for a,b in zip(pair, expected['range'])):
            return True
    return False


def project(fields):
    result = copy.deepcopy(fields)
    quantities = {}
    for key in FIELDS & fields.keys():
        value = fields[key]
        quantities[key] = copy.deepcopy(value)
        comparable = canonical(key, value)
        result[key] = None if comparable is None or comparable['ranged'] else comparable['range'][0]
    return result, quantities
