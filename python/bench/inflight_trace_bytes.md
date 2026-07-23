### In-flight trace byte limit benchmark

This benchmark isolates the byte limiter added in the parent PR. It sends 32 pre-serialized operations through the real background batch handler with 32 workers. Each operation has a 1 MiB input, 1 MiB output, and a deterministic 20 ms mock upload. Payload creation occurs before `tracemalloc` starts.

```bash
uv run python bench/inflight_trace_bytes.py
```

Python 3.14.5, Linux x86-64; medians of three runs:

| Limit | Tracemalloc peak | Elapsed |
|---:|---:|---:|
| disabled | 64.37 MiB | 0.046 s |
| 4 MiB | 2.37 MiB | 0.672 s |
| 16 MiB | 14.37 MiB | 0.111 s |
| 100 MiB | 64.37 MiB | 0.037 s |

The 4 MiB limit admits one operation because each serialized operation is slightly larger than 2 MiB after metadata. The 16 MiB limit admits seven. Peak allocation follows admitted bytes rather than worker count.

This intentionally isolates the memory/latency tradeoff; the mock sink has unlimited parallel capacity, so tighter limits increase elapsed time. In a contended real upload path, reducing oversubscription can instead improve throughput. The 100 MiB default does not constrain this 64 MiB workload, but bounds larger workloads to approximately five concurrent 20 MiB batches. Oversized batches are allowed to run alone so the limiter cannot deadlock.