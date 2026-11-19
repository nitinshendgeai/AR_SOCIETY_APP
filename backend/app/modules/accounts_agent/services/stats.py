"""Small, dependency-free robust statistics used by the detectors.

Why robust statistics: a society's expense amounts are few and skewed, and a single past outlier must not hide the next
one. The median and the median absolute deviation (MAD) are barely moved by outliers, unlike the mean and standard
deviation.
"""
from statistics import median
from typing import Iterable, List, Optional, Sequence

# Iglewicz & Hoaglin (1993): observations with a modified z-score above 3.5 are "potential outliers".
DEFAULT_Z_THRESHOLD = 3.5
# 0.6745 = the 75th percentile of the standard normal; makes MAD comparable to a standard deviation.
MAD_SCALE = 0.6745
# Below these sample sizes a spread estimate is not meaningful, so the detector stays silent rather than guess.
MIN_SAMPLES_FOR_Z = 6
MIN_SAMPLES_FOR_RECURRING = 3


def med(values: Sequence[float]) -> float:
    return float(median(values))


def mad(values: Sequence[float]) -> float:
    m = med(values)
    return med([abs(v - m) for v in values])


def modified_z(x: float, values: Sequence[float]) -> Optional[float]:
    """Modified z-score of `x` against `values` (which must not contain x itself). None when MAD is zero, i.e. the
    history shows no spread (callers then use a relative-deviation test instead)."""
    if len(values) < 2:
        return None
    d = mad(values)
    if d == 0:
        return None
    return MAD_SCALE * (x - med(values)) / d


def percentile(values: Sequence[float], q: float) -> float:
    s = sorted(values)
    if not s:
        raise ValueError("no values")
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def relative_deviation(x: float, expected: float) -> Optional[float]:
    """|x - expected| / expected, or None when expected is 0."""
    return None if not expected else abs(x - expected) / abs(expected)


def describe(values: Iterable[float]) -> dict:
    v: List[float] = [float(x) for x in values]
    if not v:
        return {"n": 0}
    return {"n": len(v), "median": med(v), "mad": mad(v), "min": min(v), "max": max(v),
            "p10": percentile(v, .10), "p90": percentile(v, .90)}
