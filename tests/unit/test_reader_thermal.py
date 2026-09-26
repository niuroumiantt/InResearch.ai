import contextlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import test_continuous_reader as fixtures
from inresearch.adapters import thermal
from inresearch.workflow import reader as cr


class Sensor:
    """Scripted temperatures; the last value repeats."""
    def __init__(self, *values):
        self.values, self.reads = list(values), 0

    def __call__(self):
        self.reads += 1
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class ThermalGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inresearch-thermal-test-")
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    def make(self, sensor, limit=85, pause=60):
        self.reader = cr.Reader(self.base / "data", self.base / "state", self.base / "repo",
                                fixtures.Model(), 0, 200, fixtures.Clock(), temperature=sensor).initialize()
        self.reader.thermal_limit, self.reader.thermal_pause = limit, pause
        p = self.reader.data / "raw-materials" / "paper.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("服务器功率为 300 W。\n这是完整正文与注释。\n", encoding="utf-8")
        return self.reader

    def run_once(self, reader):
        waits, out = [], io.StringIO()
        real_wait = threading.Event.wait

        def wait(event, timeout=None):
            if timeout == reader.thermal_pause:
                waits.append(timeout)
                return event.is_set()
            return real_wait(event, timeout)
        with mock.patch.object(threading.Event, "wait", wait), contextlib.redirect_stdout(out):
            result = reader.run(once=True)
        return result, waits, out.getvalue()

    def test_pauses_above_limit_then_resumes_after_cooling(self):
        sensor = Sensor(91.0, 86.0, 70.0)
        result, waits, out = self.run_once(self.make(sensor))
        self.assertEqual(waits, [60, 60])
        self.assertEqual(out.count('"thermal": "pause"'), 2)
        self.assertEqual(result["counts"], {"complete": 1})
        self.assertEqual(result["thermal"]["pauses"], 2)
        self.assertEqual(result["thermal"]["last_c"], 70.0)
        self.assertIsNone(result["thermal"]["paused_since"])

    def test_limit_is_strictly_greater_than(self):
        result, waits, _ = self.run_once(self.make(Sensor(85.0)))
        self.assertEqual(waits, [])
        self.assertEqual(result["counts"], {"complete": 1})

    def test_unreadable_sensor_does_not_hold_the_queue(self):
        result, waits, _ = self.run_once(self.make(Sensor(None)))
        self.assertEqual(waits, [])
        self.assertEqual(result["counts"], {"complete": 1})
        self.assertIsNone(result["thermal"]["last_c"])

    def test_zero_limit_disables_the_guard(self):
        sensor = Sensor(120.0)
        result, waits, _ = self.run_once(self.make(sensor, limit=0))
        self.assertEqual((waits, sensor.reads), ([], 0))
        self.assertEqual(result["counts"], {"complete": 1})

    def test_cool_reading_is_reused_between_quick_claims(self):
        sensor = Sensor(60.0)
        reader = self.make(sensor)
        for name, watts in (("b.txt", 400), ("c.txt", 500)):
            (reader.data / "raw-materials" / name).write_text("服务器功率为 %d W。\n" % watts, encoding="utf-8")
        result, waits, _ = self.run_once(reader)
        self.assertEqual(result["counts"], {"complete": 3})
        self.assertEqual((waits, sensor.reads), ([], 1))

    def test_without_sensor_source_guard_is_off(self):
        result, waits, _ = self.run_once(self.make(None))
        self.assertEqual(waits, [])
        self.assertEqual(result["thermal"]["pauses"], 0)


class ReadCelsiusTests(unittest.TestCase):
    def test_takes_hottest_plausible_reading_and_ignores_bogus_zones(self):
        with tempfile.TemporaryDirectory() as d:
            for i, milli in enumerate(("71500", "0", "-273000", "200000", "junk")):
                Path(d, "zone%d" % i).write_text(milli)
            smi = ("python3", "-c", "print(64)")
            self.assertEqual(thermal.read_celsius(smi, str(Path(d, "zone*"))), 71.5)

    def test_nothing_readable_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(thermal.read_celsius(("/nonexistent-nvidia-smi",), str(Path(d, "zone*"))))


if __name__ == "__main__":
    unittest.main()
