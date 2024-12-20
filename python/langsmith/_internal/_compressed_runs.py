import io
import threading

import zstandard as zstd


class CompressedRuns:
    def __init__(self):
        self.buffer = io.BytesIO()
        self.run_count = 0
        self.lock = threading.Lock()
        self.compressor_writer = zstd.ZstdCompressor(level=3, threads=-1).stream_writer(
            self.buffer, closefd=False
        )

    def reset(self):
        self.buffer = io.BytesIO()
        self.run_count = 0
        self.compressor_writer = zstd.ZstdCompressor(level=3, threads=-1).stream_writer(
            self.buffer, closefd=False
        )
