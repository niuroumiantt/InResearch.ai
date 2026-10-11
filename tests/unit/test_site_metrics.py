import copy
import unittest

from inresearch.knowledge import site_metrics, site_timeline
from tests.unit import test_site_timeline as fixtures


class SiteResourceMetricTests(unittest.TestCase):
    def metric(self, value=1000, unit='MWh', **extra):
        return dict(value=value, unit=unit, period_start='2025-01-01',
                    period_end='2025-12-31', boundary='whole campus metered electricity',
                    measurement_kind='reported', basis='native annual disclosure', **extra)

    def observation(self, ident='energy', when='2025-12-31', **fields):
        return fixtures.SiteTimelineTests().native(ident, when, **fields)

    def test_energy_and_power_and_flow_never_interchange(self):
        for key, unit in [('electricity_consumption_mwh', 'MW'),
                          ('water_consumption_m3', 'm³/day'),
                          ('water_use_m3_per_day', 'm³'), ('pue', 'L/kWh IT')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'dimension'):
                site_metrics.check(key, self.metric(unit=unit))
        self.assertFalse(site_metrics.supported('electricity_consumption_mwh', self.metric(), '1000 MW capacity'))

    def test_native_interval_keeps_bounds_and_cannot_supply_a_midpoint(self):
        metric=self.metric();metric.pop('value');metric['value_range']=[1,2];metric['unit']='GWh'
        row=self.observation(electricity_consumption_mwh=metric)
        result=site_timeline.current({'observations':[row]}, '2026-10-11')
        self.assertIsNone(result['electricity_consumption_mwh'])
        self.assertEqual(result['quantity_fields']['electricity_consumption_mwh'],metric)
        self.assertTrue(site_metrics.supported('electricity_consumption_mwh',metric,'Campus usage was 1–2 GWh.'))
        self.assertFalse(site_metrics.supported('electricity_consumption_mwh',metric,'Campus usage was 1 GWh and another campus used 2 GWh.'))

    def test_units_compare_without_overwriting_native_period_or_other_indicators(self):
        a=self.observation('a',electricity_consumption_mwh=self.metric())
        b=self.observation('b',electricity_consumption_mwh=self.metric(1,'GWh'))
        water=self.metric(500,'m³');water['boundary']='whole campus consumed water'
        w=self.observation('water',water_consumption_m3=water)
        row={'observations':[a,b,w]};original=copy.deepcopy(row)
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['electricity_consumption_mwh'],1000)
        self.assertEqual(result['water_consumption_m3'],500)
        self.assertFalse(result['tracking']['conflicts'])
        self.assertEqual(row,original)
        b['fields']['electricity_consumption_mwh']['period_start']='2025-07-01'
        self.assertTrue(site_timeline.current(row,'2026-10-11')['tracking']['conflicts'])

    def test_reporting_boundary_and_unknown_period_are_explicit(self):
        row=self.metric();row['period_start']=row['period_end']=None
        site_metrics.check('electricity_consumption_mwh',row)
        for key in ['boundary','period_start','period_end','measurement_kind']:
            bad=copy.deepcopy(row);bad.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):
                site_metrics.check('electricity_consumption_mwh',bad)
        row['measurement_kind']='estimated'
        with self.assertRaisesRegex(ValueError,'assumptions'):
            site_metrics.check('electricity_consumption_mwh',row)

    def test_forecasts_and_phase_measurements_never_enter_current_whole_site(self):
        a=self.observation('actual',electricity_consumption_mwh=self.metric())
        b=self.observation('forecast','2026-01-01',electricity_consumption_mwh=self.metric(2000));b['kind']='forecast'
        c=self.observation('phase','2026-01-01',electricity_consumption_mwh=self.metric(500));c['scope']='phase:building-b'
        result=site_timeline.current({'observations':[a,b,c]},'2026-10-11')
        self.assertEqual(result['electricity_consumption_mwh'],1000)
        self.assertEqual(result['tracking']['forecasts'],1)
        self.assertEqual(result['scope_views']['phase:building-b']['electricity_consumption_mwh'],500)
