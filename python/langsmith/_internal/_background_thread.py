from __future__ import annotations

import functools
import logging
import sys
import threading
import weakref
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from queue import Empty, Queue
from typing import (
    TYPE_CHECKING,
    List,
    Union,
    cast,
)

from langsmith import schemas as ls_schemas
from langsmith._internal._constants import (
    _AUTO_SCALE_DOWN_NEMPTY_TRIGGER,
    _AUTO_SCALE_UP_NTHREADS_LIMIT,
    _AUTO_SCALE_UP_QSIZE_TRIGGER,
)
from langsmith._internal._multipart import (
    MultipartPartsAndContext,
    SerializedFeedbackOperation,
    SerializedRunOperation,
    join_multipart_parts_and_context,
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
    item_by_action = defaultdict(list)
    for i in batch:
        item_by_action[i.item[0]].append(i.item[1])
    if use_multipart:
        if "create" in item_by_action:
            # convert create items to create-multipart items
            # TODO
            pass
        if "update" in item_by_action:
            # convert update items to update-multipart items
            # TODO
            pass
    else:
        if any(
            k in item_by_action
            for k in ("create-multipart", "update-multipart", "feedback-multipart")
        ):
            logger.error(
                "Multipart items found in queue, but use_multipart is False. "
                "This should not happen."
            )
            item_by_action.pop("create-multipart", None)
            item_by_action.pop("update-multipart", None)
            item_by_action.pop("feedback-multipart", None)
    try:
        # sent multipart request
        acc_multipart = join_multipart_parts_and_context(
            cast(MultipartPartsAndContext, i)
            for i in chain(
                item_by_action["create-multipart"], item_by_action["update-multipart"]
            )
        )
        if acc_multipart:
            client._send_multipart_req(acc_multipart)

        # sent batch request
        create = item_by_action["create"]
        update = item_by_action["update"]
        if create or update:
            client.batch_ingest_runs(
                create=cast(List[_RunData], create),
                update=cast(List[_RunData], update),
                pre_sampled=True,
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
