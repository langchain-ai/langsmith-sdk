import io
import threading
from typing import Optional

from langsmith import utils as ls_utils

try:
    from zstandard import ZstdCompressor  # type: ignore[import]

    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

compression_level = int(ls_utils.get_env_var("RUN_COMPRESSION_LEVEL") or 1)

# One zstd worker, not one per logical CPU: every worker holds its own job's
# uncompressed input until it is consumed, so `threads=-1` kept ~the whole batch
# in RAM on many-core hosts. Compression still runs off the caller's thread.
# `RUN_COMPRESSION_THREADS=0` compresses inline on the tracing thread instead.
_compression_threads_env = ls_utils.get_env_var("RUN_COMPRESSION_THREADS")
compression_threads = (
    int(_compression_threads_env) if _compression_threads_env is not None else 1
)

DEFAULT_MAX_UNCOMPRESSED_QUEUE_BYTES = 1024 * 1024 * 1024  # 1GB


class CompressedTraces:
    def __init__(self, max_uncompressed_size_bytes: Optional[int] = None) -> None:
        if not ZSTD_AVAILABLE:
            raise ImportError(
                "zstandard is required for compressed trace ingestion. "
                "Install it with `pip install zstandard` or set the environment "
                "variable LANGSMITH_DISABLE_RUN_COMPRESSION=true to disable "
                "compression."
            )
        # Configure the maximum total uncompressed size for the in-memory queue.
        if max_uncompressed_size_bytes is None:
            max_bytes_str = ls_utils.get_env_var("MAX_INGEST_MEMORY_BYTES")
            if max_bytes_str is not None:
                max_uncompressed_size_bytes = int(max_bytes_str)
            else:
                max_uncompressed_size_bytes = DEFAULT_MAX_UNCOMPRESSED_QUEUE_BYTES

        self.max_uncompressed_size_bytes = max_uncompressed_size_bytes

        self.buffer: io.BytesIO = io.BytesIO()
        self.trace_count: int = 0
        self.lock = threading.Lock()
        self.uncompressed_size: int = 0
        self._context: list[str] = []
        # Where this frame goes. Sent verbatim to each, so all ops in one frame
        # must share it. Claimed by the first op written, released when the frame
        # is sent, so a client whose replicas change is not stuck on the first set.
        self.destinations: Optional[frozenset] = None

        self.compressor_writer = ZstdCompressor(
            level=compression_level, threads=compression_threads
        ).stream_writer(self.buffer, closefd=False)

    def accepts(self, destinations: frozenset) -> bool:
        """Report whether an op for `destinations` may join this frame.

        Hold self.lock; commit and write in the same hold.
        """
        return self.destinations is None or self.destinations == destinations

    def reset(self) -> None:
        # The next op claims the new frame, whatever its destinations.
        self.destinations = None
        self.buffer = io.BytesIO()
        self.trace_count = 0
        self.uncompressed_size = 0
        self._context = []
        self.compressor_writer = ZstdCompressor(
            level=compression_level, threads=compression_threads
        ).stream_writer(self.buffer, closefd=False)
