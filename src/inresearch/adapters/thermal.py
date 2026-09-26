"""Machine temperature for long-running local inference.

Reads the GPU through nvidia-smi and every kernel thermal zone, and reports the
hottest plausible reading in degrees Celsius. None means nothing was readable;
callers decide what that means, this module never guesses a temperature."""
from __future__ import annotations
import glob
import subprocess

NVIDIA_SMI = ("nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits")
THERMAL_ZONES = "/sys/class/thermal/thermal_zone*/temp"
# Disconnected sensors report 0, -273 or saturated values; none of them is a machine temperature.
PLAUSIBLE = (0.0, 150.0)


def _plausible(value):
    return PLAUSIBLE[0] < value < PLAUSIBLE[1]


def read_celsius(smi=NVIDIA_SMI, zones=THERMAL_ZONES, timeout=10):
    values = []
    try:
        out = subprocess.run(list(smi), capture_output=True, text=True, timeout=timeout, check=True).stdout
        values.extend(float(v) for v in out.split())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    for path in glob.glob(zones):
        try:
            with open(path, encoding="ascii") as f:
                values.append(int(f.read().strip()) / 1000)
        except (OSError, ValueError):
            pass
    values = [v for v in values if _plausible(v)]
    return max(values) if values else None
