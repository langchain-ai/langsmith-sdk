"""Measure trace-upload concurrency under byte-weighted limits."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from types import SimpleNamespace
from typing import Any

from langsmith._internal._background_thread import (
    TracingQueueItem,
    _tracing_thread_handle_batch,
)
from langsmith._internal._inflight import TracingBytesLimiter
from langsmith._internal._operations import SerializedRunOperation

MIB = 1024 * 1024


def make_batch(payload_bytes: int, sequence: int) -> list[TracingQueueItem]:
    run_id = uuid.uuid5(uuid.NAMESPACE_URL, f"inflight-benchmark-{sequence}")
    operation = SerializedRunOperation(
        operation="post",
        id=run_id,
        trace_id=run_id,
        _none=b'"metadata"',
        inputs=b"i" * payload_bytes,
        outputs=b"o" * payload_bytes,
    )
    return [TracingQueueItem(f"{sequence:08}", operation)]


def measure(
    *,
    limit_mib: int,
    workers: int,
    operations: int,
    payload_mib: int,
    upload_delay: float,
) -> dict[str, Any]:
    batches = [
        make_batch(payload_mib * MIB, sequence) for sequence in range(operations)
    ]
    limiter = TracingBytesLimiter(limit_mib * MIB)

    def ingest(ops: list[SerializedRunOperation], **kwargs: Any) -> None:
        body = b"".join(
            part
            for operation in ops
            for part in (operation.inputs, operation.outputs)
            if part is not None
        )
        time.sleep(upload_delay)
        if len(body) != payload_mib * MIB * 2:
            raise AssertionError("Unexpected synthetic upload size")

    client = SimpleNamespace(
        _tracing_inflight_limiter=limiter,
        _multipart_ingest_ops=ingest,
        _invoke_tracing_error_callback=lambda error: None,
    )

    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _tracing_thread_handle_batch,
                client,
                Queue(),
                batch,
                True,
                False,
            )
            for batch in batches
        ]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "limit_mib": limit_mib,
        "workers": workers,
        "operations": operations,
        "payload_mib_per_field": payload_mib,
        "serialized_mib_per_operation": payload_mib * 2,
        "elapsed_seconds": elapsed,
        "tracemalloc_peak_mib": peak_bytes / MIB,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limits-mib", default="0,4,16,100")
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--operations", type=int, default=32)
    parser.add_argument("--payload-mib", type=int, default=1)
    parser.add_argument("--upload-delay", type=float, default=0.02)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()

    for limit in (int(value) for value in args.limits_mib.split(",")):
        samples = [
            measure(
                limit_mib=limit,
                workers=args.workers,
                operations=args.operations,
                payload_mib=args.payload_mib,
                upload_delay=args.upload_delay,
            )
            for _ in range(args.repetitions)
        ]
        print(
            json.dumps(
                {
                    "limit_mib": limit,
                    "elapsed_seconds_median": statistics.median(
                        sample["elapsed_seconds"] for sample in samples
                    ),
                    "tracemalloc_peak_mib_median": statistics.median(
                        sample["tracemalloc_peak_mib"] for sample in samples
                    ),
                    "samples": samples,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
