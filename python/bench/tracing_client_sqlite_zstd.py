from bench.utils import create_large_json
from uuid import uuid4
from datetime import datetime, timezone
import time
import threading
import sqlite3
import zstandard as zstd
import io
import os
import orjson
from memory_profiler import profile

NUM_RUNS = 0
INSERT_STMT = '''
    INSERT INTO runs (run_id, dotted_order, inputs, outputs)
    VALUES (?, ?, ?, ?)
'''
NUM_THREADS = 1
BATCH_SIZE = 1000  # Increased batch size for bulk operations

def process_batch(cursor, compressor, last_processed_dotted_order, batch_size):
    """Process a single batch of runs and return the count and last processed order."""
    # Fetch runs after our last processed order
    res = cursor.execute('''
        SELECT run_id, inputs, outputs, dotted_order
        FROM runs 
        WHERE dotted_order > ?
        ORDER BY dotted_order 
        LIMIT ?;
    ''', (last_processed_dotted_order or '', batch_size))

    # Process runs one at a time using cursor iterator
    zstd_buffer = io.BytesIO()
    run_count = 0
    last_order = last_processed_dotted_order

    with compressor.stream_writer(zstd_buffer) as compressor_stream:
        for run_id, inputs_blob, outputs_blob, dotted_order in res:
            run_count += 1
            # Decompress the inputs and outputs
            inputs_blob = zstd.decompress(inputs_blob)
            outputs_blob = zstd.decompress(outputs_blob)
            data = inputs_blob + b'\n' + outputs_blob + b'\n'
            compressor_stream.write(data)
            last_order = dotted_order
        compressed_size = zstd_buffer.tell()

    if compressed_size > 0:
        # Simulate network latency
        time.sleep(0.150)
        global NUM_RUNS
        NUM_RUNS += run_count

    return run_count, last_order

def run_processor(db_file, stop_event):
    """Background thread function to fetch runs and process them."""
    conn = sqlite3.connect(db_file, timeout=30)
    cursor = conn.cursor()

    compressor = zstd.ZstdCompressor(level=3)
    batch_size = 300
    last_processed_dotted_order = None

    try:
        while not stop_event.is_set():
            run_count, last_processed_dotted_order = process_batch(
                cursor,
                compressor,
                last_processed_dotted_order,
                batch_size
            )

        # Drain remaining runs
        while True:
            run_count, last_processed_dotted_order = process_batch(
                cursor,
                compressor,
                last_processed_dotted_order,
                batch_size
            )
            if run_count == 0:
                break

    finally:
        conn.close()

def generate_run_data(num_runs, inputs_blob, outputs_blob):
    """Generator function to create run data for bulk insertion."""
    for _ in range(num_runs):
        run_id = str(uuid4())
        start_time = datetime.now(timezone.utc)
        dotted_order = f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"
        yield (run_id, dotted_order, inputs_blob, outputs_blob)

@profile
def benchmark_run_creation(json_size, num_runs) -> None:
    """Benchmark the creation of runs using executemany."""
    # Delete the existing database file
    if os.path.exists('runs.db'):
        os.remove('runs.db')

    db_file = 'runs.db'
    # Initialize SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Optimize PRAGMA settings
    cursor.execute('PRAGMA journal_mode=MEMORY;')
    cursor.execute('PRAGMA synchronous=OFF;')
    cursor.execute('PRAGMA temp_store=MEMORY;')
    cursor.execute('PRAGMA locking_mode=EXCLUSIVE;')
    cursor.execute('PRAGMA cache_size=-64000;')  # 64MB cache
    cursor.execute('PRAGMA mmap_size=268435456;')  # 256MB mmap

    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            dotted_order TEXT,
            inputs BLOB,
            outputs BLOB
        );
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_status_dotted_order 
        ON runs(dotted_order);
    ''')
    conn.commit()

    print("Creating runs...")
    # Create and compress inputs and outputs once
    inputs = create_large_json(json_size)
    outputs = create_large_json(json_size)
    inputs_blob = zstd.compress(orjson.dumps(inputs))
    outputs_blob = zstd.compress(orjson.dumps(outputs))
    print("Runs created.")

    stop_event = threading.Event()
    processor_threads = []
    for _ in range(NUM_THREADS):
        processor_thread = threading.Thread(target=run_processor, args=(db_file, stop_event))
        processor_thread.start()
        processor_threads.append(processor_thread)

    start = time.perf_counter()

    # Begin a transaction
    cursor.execute('BEGIN TRANSACTION;')

    # Use executemany with a generator for bulk insertion
    cursor.executemany(
        INSERT_STMT,
        generate_run_data(num_runs, inputs_blob, outputs_blob)
    )

    # Commit the transaction
    conn.commit()

    # Close the main thread's database connection
    conn.close()

    # Signal the processor thread to stop
    stop_event.set()

    # Join the processor threads
    for processor_thread in processor_threads:
        processor_thread.join()

    print("Time taken to insert runs: ", time.perf_counter() - start)
    print("Total runs processed: ", NUM_RUNS)

def main():
    """Run benchmarks with specified parameters."""
    json_size = 5_000
    num_runs = 10_000

    benchmark_run_creation(json_size, num_runs)

if __name__ == "__main__":
    main()