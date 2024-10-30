from __future__ import annotations

import collections
import functools
import logging
import sys
import threading
import weakref
from dataclasses import dataclass
from queue import Empty, Queue
from typing import (
    TYPE_CHECKING,
    DefaultDict,
    List,
    Literal,
    Union,
    cast,
)

import orjson

from langsmith import schemas as ls_schemas
from langsmith._internal._constants import (
    _AUTO_SCALE_DOWN_NEMPTY_TRIGGER,
    _AUTO_SCALE_UP_NTHREADS_LIMIT,
    _AUTO_SCALE_UP_QSIZE_TRIGGER,
    _SIZE_LIMIT_BYTES,
)
from langsmith._internal._multipart import (
    MultipartPartsAndContext,
    SerializedFeedbackOperation,
    SerializedRunOperation,
    join_multipart_parts_and_context,
    serialized_feedback_operation_to_multipart_parts_and_context,
    serialized_run_operation_to_multipart_parts_and_context,
)

if TYPE_CHECKING:
    from langsmith.client import Client

logger = logging.getLogger("langsmith.client")

_RunData = Union[ls_schemas.Run, ls_schemas.RunLikeDict, dict]


@functools.total_ordering
@dataclass
class TracingQueueItem:
    """An item in the tracing queue.

    Attributes:
        priority (str): The priority of the item.
        action (str): The action associated with the item.
        item (Any): The item itself.
    """

    priority: str
    item: Union[SerializedRunOperation, SerializedFeedbackOperation]

    def __lt__(self, other: TracingQueueItem) -> bool:
        return (self.priority, self.item.__class__) < (
            other.priority,
            other.item.__class__,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TracingQueueItem) and (
            self.priority,
            self.item.__class__,
        ) == (other.priority, other.item.__class__)


def _tracing_thread_drain_queue(
    tracing_queue: Queue, limit: int = 100, block: bool = True
) -> List[TracingQueueItem]:
    next_batch: List[TracingQueueItem] = []
    try:
        # wait 250ms for the first item, then
        # - drain the queue with a 50ms block timeout
        # - stop draining if we hit the limit
        # shorter drain timeout is used instead of non-blocking calls to
        # avoid creating too many small batches
        if item := tracing_queue.get(block=block, timeout=0.25):
            next_batch.append(item)
        while item := tracing_queue.get(block=block, timeout=0.05):
            next_batch.append(item)
            if limit and len(next_batch) >= limit:
                break
    except Empty:
        pass
    return next_batch


def _tracing_thread_handle_batch(
    client: Client,
    tracing_queue: Queue,
    batch: List[TracingQueueItem],
    use_multipart: bool,
) -> None:
    try:
        if use_multipart:
            parts: list[MultipartPartsAndContext] = []
            for item in batch:
                if isinstance(item.item, SerializedRunOperation):
                    parts.append(
                        serialized_run_operation_to_multipart_parts_and_context(
                            item.item
                        )
                    )
                elif isinstance(item.item, SerializedFeedbackOperation):
                    parts.append(
                        serialized_feedback_operation_to_multipart_parts_and_context(
                            item.item
                        )
                    )
                else:
                    logger.error("Unknown item type in tracing queue: %s", item)
            acc_multipart = join_multipart_parts_and_context(parts)
            if acc_multipart:
                client._send_multipart_req(acc_multipart)
        else:
            ids_and_partial_body: dict[
                Literal["post", "patch"], list[tuple[str, bytes]]
            ] = {
                "post": [],
                "patch": [],
            }

            # form the partial body and ids
            for item in batch:
                op = item.item
                if isinstance(op, SerializedRunOperation):
                    curr_dict = orjson.loads(op._none)
                    if op.inputs:
                        curr_dict["inputs"] = orjson.Fragment(op.inputs)
                    if op.outputs:
                        curr_dict["outputs"] = orjson.Fragment(op.outputs)
                    if op.events:
                        curr_dict["events"] = orjson.Fragment(op.events)
                    if op.attachments:
                        logger.warning(
                            "Attachments are not supported in non-multipart mode"
                        )
                    ids_and_partial_body[op.operation].append(
                        (f"trace={op.trace_id},id={op.id}", orjson.dumps(curr_dict))
                    )
                elif isinstance(op, SerializedFeedbackOperation):
                    logger.warning(
                        "Feedback operations are not supported in non-multipart mode"
                    )
                else:
                    logger.error("Unknown item type in tracing queue: %s", item)

            # send the requests in batches
            info = client.info
            size_limit_bytes = (info.batch_ingest_config or {}).get(
                "size_limit_bytes"
            ) or _SIZE_LIMIT_BYTES

            body_chunks: DefaultDict[str, list] = collections.defaultdict(list)
            context_ids: DefaultDict[str, list] = collections.defaultdict(list)
            body_size = 0
            for key in cast(list[Literal["post", "patch"]], ["post", "patch"]):
                body_deque = collections.deque(ids_and_partial_body[key])
                while body_deque:
                    if (
                        body_size > 0
                        and body_size + len(body_deque[0][1]) > size_limit_bytes
                    ):
                        client._post_batch_ingest_runs(
                            orjson.dumps(body_chunks),
                            _context=f"\n{key}: {'; '.join(context_ids[key])}",
                        )
                        body_size = 0
                        body_chunks.clear()
                        context_ids.clear()
                    curr_id, curr_body = body_deque.popleft()
                    body_size += len(curr_body)
                    body_chunks[key].append(orjson.Fragment(curr_body))
                    context_ids[key].append(curr_id)
            if body_size:
                context = "; ".join(
                    f"{k}: {'; '.join(v)}" for k, v in context_ids.items()
                )
                client._post_batch_ingest_runs(
                    orjson.dumps(body_chunks), _context="\n" + context
                )

    except Exception:
        logger.error("Error in tracing queue", exc_info=True)
        # exceptions are logged elsewhere, but we need to make sure the
        # background thread continues to run
        pass
    finally:
        for _ in batch:
            tracing_queue.task_done()


def _ensure_ingest_config(
    info: ls_schemas.LangSmithInfo,
) -> ls_schemas.BatchIngestConfig:
    default_config = ls_schemas.BatchIngestConfig(
        use_multipart_endpoint=False,
        size_limit_bytes=None,  # Note this field is not used here
        size_limit=100,
        scale_up_nthreads_limit=_AUTO_SCALE_UP_NTHREADS_LIMIT,
        scale_up_qsize_trigger=_AUTO_SCALE_UP_QSIZE_TRIGGER,
        scale_down_nempty_trigger=_AUTO_SCALE_DOWN_NEMPTY_TRIGGER,
    )
    if not info:
        return default_config
    try:
        if not info.batch_ingest_config:
            return default_config
        return info.batch_ingest_config
    except BaseException:
        return default_config


def tracing_control_thread_func(client_ref: weakref.ref[Client]) -> None:
    client = client_ref()
    if client is None:
        return
    tracing_queue = client.tracing_queue
    assert tracing_queue is not None
    batch_ingest_config = _ensure_ingest_config(client.info)
    size_limit: int = batch_ingest_config["size_limit"]
    scale_up_nthreads_limit: int = batch_ingest_config["scale_up_nthreads_limit"]
    scale_up_qsize_trigger: int = batch_ingest_config["scale_up_qsize_trigger"]
    use_multipart = batch_ingest_config.get("use_multipart_endpoint", False)

    sub_threads: List[threading.Thread] = []
    # 1 for this func, 1 for getrefcount, 1 for _get_data_type_cached
    num_known_refs = 3

    # loop until
    while (
        # the main thread dies
        threading.main_thread().is_alive()
        # or we're the only remaining reference to the client
        and sys.getrefcount(client) > num_known_refs + len(sub_threads)
    ):
        for thread in sub_threads:
            if not thread.is_alive():
                sub_threads.remove(thread)
        if (
            len(sub_threads) < scale_up_nthreads_limit
            and tracing_queue.qsize() > scale_up_qsize_trigger
        ):
            new_thread = threading.Thread(
                target=_tracing_sub_thread_func,
                args=(weakref.ref(client), use_multipart),
            )
            sub_threads.append(new_thread)
            new_thread.start()
        if next_batch := _tracing_thread_drain_queue(tracing_queue, limit=size_limit):
            _tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
    # drain the queue on exit
    while next_batch := _tracing_thread_drain_queue(
        tracing_queue, limit=size_limit, block=False
    ):
        _tracing_thread_handle_batch(client, tracing_queue, next_batch, use_multipart)


def _tracing_sub_thread_func(
    client_ref: weakref.ref[Client],
    use_multipart: bool,
) -> None:
    client = client_ref()
    if client is None:
        return
    try:
        if not client.info:
            return
    except BaseException as e:
        logger.debug("Error in tracing control thread: %s", e)
        return
    tracing_queue = client.tracing_queue
    assert tracing_queue is not None
    batch_ingest_config = _ensure_ingest_config(client.info)
    size_limit = batch_ingest_config.get("size_limit", 100)
    seen_successive_empty_queues = 0

    # loop until
    while (
        # the main thread dies
        threading.main_thread().is_alive()
        # or we've seen the queue empty 4 times in a row
        and seen_successive_empty_queues
        <= batch_ingest_config["scale_down_nempty_trigger"]
    ):
        if next_batch := _tracing_thread_drain_queue(tracing_queue, limit=size_limit):
            seen_successive_empty_queues = 0
            _tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
        else:
            seen_successive_empty_queues += 1

    # drain the queue on exit
    while next_batch := _tracing_thread_drain_queue(
        tracing_queue, limit=size_limit, block=False
    ):
        _tracing_thread_handle_batch(client, tracing_queue, next_batch, use_multipart)
