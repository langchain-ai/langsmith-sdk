from pyperf._runner import Runner

from bench.cases import BENCHMARKS

r = Runner()

for name, fn, input_ in BENCHMARKS:
    r.bench_func(name, fn, input_)
