"""pytest-benchmark port of the pyperf suite in ``bench/__main__.py``.

Run via ``make benchmark-pytest``. In CI the Datadog action sets
``PYTEST_ADDOPTS=--ddtrace``, and ddtrace's pytest-benchmark integration ships
the timings to Datadog Test Optimization; no extra wiring here.
"""

import pytest

from bench.cases import BENCHMARKS


@pytest.mark.parametrize(
    ("fn", "input_"),
    [(fn, input_) for _, fn, input_ in BENCHMARKS],
    ids=[name for name, _, _ in BENCHMARKS],
)
def test_bench(benchmark, fn, input_):
    benchmark(fn, input_)
