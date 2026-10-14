---
type: performance capture
title: Measured Trace Ingestion Paths
description: Durable timing capture comparing bulk trace-ingestion routes through direct, batched, multipart, compressed, OpenTelemetry, and hybrid paths. Preserves call counts, wire sizes, thread handoffs, flush boundaries, and per-path event timelines.
tags: [tracing, ingestion, performance, batching, opentelemetry, python]
sources:
  - id: openwiki-source-197446e566d18b5ec23537cc
    resource: repo://python/langsmith/client.py
verified:
  - by: openwiki/0.5.2
    at: 2026-09-15T09:58:29.947Z
generated: { by: "openwiki/0.5.2", at: "2026-09-15T09:52:25.586Z" }
---

# Measured Trace Ingestion Paths

This capture measured a 60-run application producing 120 operations—a post on enter and a patch on exit—against the trace lab's fake LangSmith backend, which answered in 20 ms per ingest request. **End to end** spans the first through last log record, while **App thread busy** spans rows on the application's own thread; the gap indicates work that moved off that thread.

The timings are from one capture and are rounded to 10 ms. Call counts, part counts, and byte sizes are stable across captures. For implementation details and interpretation of endpoint, queue, thread, retry, and flush boundaries, see [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md).

## Route comparison

| Path | HTTP calls | End to end | App thread busy | Bytes on the wire | `post.*` parts | `patch.*` parts |
|---|---|---|---|---|---|---|
| `/runs` | 120 | 3,500 ms | 3,500 ms (100%) | 109,180 | — | — |
| `/runs/batch` | 2 | 260 ms | 170 ms (67%) | 55,500 | — | — |
| `/runs/multipart` | 2 | 360 ms | 200 ms (54%) | 106,976 | 300 | — |
| `/runs/multipart+zstd` | 2 | 270 ms | 240 ms (89%) | 6,488 | 300 | 240 |
| `/otel` | 1 | 360 ms | 320 ms (89%) | 40,987 | — | — |
| `hybrid` | 3 | 460 ms | 430 ms (93%) | 147,963 | 300 | — |

## Per-path storylines

## `/runs` -- 120 call(s): 60 × POST /runs, 60 × PATCH /runs/<id>

| At | Thread | Step | What happened |
|---|---|---|---|
| ~70 ms | — | `[14]` | 60 × app: POST /runs …B, 60 × app: PATCH /runs/step …B |
| ~3,500 ms | app | `[15]` | flush() |

## `/runs/batch` -- 2 call(s): 2 × POST /runs/batch

| At | Thread | Step | What happened |
|---|---|---|---|
| ~10 ms | tracing | `[00]` | no zstd frame (backend /info: no multipart) → queue to /runs/batch |
| ~150 ms | tracing | `[12]` | drained 100 queue items |
| ~150 ms | tracing | `[13]` | combine 100 ops → 50 |
| ~150 ms | tracing | `[14]` | POST /runs/batch 46240B |
| ~170 ms | app | `[15]` | flush() |
| ~240 ms | tracing | `[12]` | drained 20 queue items |
| ~240 ms | tracing | `[13]` | combine 20 ops → 10 |
| ~240 ms | tracing | `[14]` | POST /runs/batch 9260B |

## `/runs/multipart` -- 2 call(s): 2 × POST /runs/multipart

| At | Thread | Step | What happened |
|---|---|---|---|
| ~160 ms | tracing | `[12]` | drained 100 queue items |
| ~160 ms | tracing | `[13]` | combine 100 ops → 50 |
| ~180 ms | tracing | `[14]` | POST /runs/multipart 89118B |
| ~200 ms | app | `[15]` | flush() |
| ~340 ms | tracing | `[12]` | drained 20 queue items |
| ~340 ms | tracing | `[13]` | combine 20 ops → 10 |
| ~340 ms | tracing | `[14]` | POST /runs/multipart 17858B |

## `/runs/multipart+zstd` -- 2 call(s): 2 × POST /runs/multipart

| At | Thread | Step | What happened |
|---|---|---|---|
| ~10 ms | tracing | `[00]` | zstd frame BUILT (level 1, cap 1073741824B) |
| ~200 ms | compress | `[12]` | frame closed [data available, 100-op limit] 86630→4935B (17.6x) |
| ~200 ms | compress | `[12b]` | send frame: 4935B to 1 dest |
| ~200 ms | compress | `[14]` | POST /runs/multipart 4935B zstd |
| ~240 ms | app | `[15]` | flush() |
| ~240 ms | app | `[12]` | frame closed [flush(), forced, whatever is buffered] 17330→1553B (11.2x) |
| ~240 ms | compress | `[12b]` | send frame: 1553B to 1 dest |
| ~240 ms | app | `[15b]` | flush waits on 2 in-flight send(s) |
| ~240 ms | compress | `[14]` | POST /runs/multipart 1553B zstd |

## `/otel` -- 1 call(s): 1 × POST /otel

| At | Thread | Step | What happened |
|---|---|---|---|
| ~0 ms | app | `[21c]` | OTLP target: POST /otel |
| ~0 ms | app | `[21]` | OTEL path BUILT (built its own provider) |
| ~10 ms | tracing | `[00]` | no zstd frame (tracing_mode=otel) → queue to /runs/multipart |
| ~200 ms | tracing | `[13]` | combine 100 ops → 50 |
| ~200 ms | tracing | `[23]` | otel leg: 50 run op(s), 0 dropped |
| ~200 ms | tracing | `[24]` | export_batch: 50 post, 0 patch (0 open) |
| ~220 ms | — | `[26]` | 60 × otel: OTLP export: step (13 attrs) |
| ~260 ms | app | `[15]` | flush() |
| ~310 ms | tracing | `[13]` | combine 20 ops → 10 |
| ~310 ms | tracing | `[23]` | otel leg: 10 run op(s), 0 dropped |
| ~310 ms | tracing | `[24]` | export_batch: 10 post, 0 patch (50 open) |
| ~320 ms | app | `[15c]` | flush() does not cover OTEL (60 span(s) open) |

## `hybrid` -- 3 call(s): 2 × POST /runs/multipart, 1 × POST /otel

| At | Thread | Step | What happened |
|---|---|---|---|
| ~0 ms | app | `[21c]` | OTLP target: POST /otel |
| ~0 ms | app | `[21]` | OTEL path BUILT (built its own provider) |
| ~10 ms | tracing | `[00]` | no zstd frame (tracing_mode=hybrid) → queue to /runs/multipart |
| ~180 ms | tracing | `[13]` | combine 100 ops → 50 |
| ~180 ms | tracing | `[23c]` | hybrid: 50 op(s) both ways, one thread |
| ~180 ms | tracing | `[12]` | drained 100 queue items |
| ~200 ms | tracing | `[14]` | POST /runs/multipart 89118B |
| ~220 ms | app | `[15]` | flush() |
| ~300 ms | tracing | `[23]` | otel leg: 50 run op(s), 0 dropped |
| ~300 ms | tracing | `[24]` | export_batch: 50 post, 0 patch (0 open) |
| ~330 ms | — | `[26]` | 60 × otel: OTLP export: step (13 attrs) |
| ~370 ms | tracing | `[13]` | combine 20 ops → 10 |
| ~370 ms | tracing | `[23c]` | hybrid: 10 op(s) both ways, one thread |
| ~370 ms | tracing | `[12]` | drained 20 queue items |
| ~380 ms | tracing | `[14]` | POST /runs/multipart 17858B |
| ~420 ms | tracing | `[23]` | otel leg: 10 run op(s), 0 dropped |
| ~420 ms | tracing | `[24]` | export_batch: 10 post, 0 patch (50 open) |
| ~430 ms | app | `[15c]` | flush() does not cover OTEL (60 span(s) open) |

## Provenance

The capture was generated on the `learn/trace-ingest-logs` branch by `python/trace_lab/build_timeline.py --app bulk --md`. This wiki page is the durable copy of the committed capture.

## Related pages

- [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md)
- [Run Tree and Context](/openwiki/concepts/run-tree-and-context.md)
- [Repository Test Strategy](/openwiki/testing/repository-test-strategy.md)
