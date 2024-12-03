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
BATCH_SIZE = 1000

def process_batch(conn, compressor, last_processed_dotted_order, batch_size):
    """Process a single batch of runs and return the count and last processed order."""
    # Fetch runs after our last processed order using connection directly
    query_results = conn.execute('''
        SELECT run_id, inputs, outputs, dotted_order
        FROM runs 
        WHERE dotted_order > ?
        ORDER BY dotted_order 
        LIMIT ?;
    ''', (last_processed_dotted_order or '', batch_size))

    # Process runs using iterator
    zstd_buffer = io.BytesIO()
    run_count = 0
    last_order = last_processed_dotted_order

    with compressor.stream_writer(zstd_buffer) as compressor_stream:
        for run_id, inputs_blob, outputs_blob, dotted_order in query_results:
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
    compressor = zstd.ZstdCompressor(level=3)
    batch_size = 300
    last_processed_dotted_order = None

    try:
        while not stop_event.is_set():
            run_count, last_processed_dotted_order = process_batch(
                conn,
                compressor,
                last_processed_dotted_order,
                batch_size
            )

        # Drain remaining runs
        while True:
            run_count, last_processed_dotted_order = process_batch(
                conn,
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
    """Benchmark the creation of runs using executemany without cursors and with postponed indexing."""
    # Delete the existing database file
    if os.path.exists('runs.db'):
        os.remove('runs.db')

    db_file = 'runs.db'
    # Initialize SQLite database
    conn = sqlite3.connect(db_file)

    # Optimize PRAGMA settings
    conn.execute('PRAGMA journal_mode=MEMORY;')
    conn.execute('PRAGMA synchronous=OFF;')
    conn.execute('PRAGMA temp_store=MEMORY;')
    conn.execute('PRAGMA locking_mode=EXCLUSIVE;')
    conn.execute('PRAGMA cache_size=-64000;')  # 64MB cache
    conn.execute('PRAGMA mmap_size=268435456;')  # 256MB mmap

    # Create table without indices
    conn.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            dotted_order TEXT,
            inputs BLOB,
            outputs BLOB
        );
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
    insert_start = time.perf_counter()

    # Begin a transaction for data insertion
    conn.execute('BEGIN TRANSACTION;')

    # Use executemany directly on the connection
    conn.executemany(
        INSERT_STMT,
        generate_run_data(num_runs, inputs_blob, outputs_blob)
    )

    # Commit the insertion transaction
    conn.commit()
    
    print(f"Time taken for insertions: {time.perf_counter() - insert_start:.2f} seconds")
    
    # Create indices after all data is inserted
    index_start = time.perf_counter()
    print("Creating indices...")
    
    # Begin a new transaction for index creation
    conn.execute('BEGIN TRANSACTION;')
    
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_status_dotted_order 
        ON runs(dotted_order);
    ''')
        
    # Commit the index creation transaction
    conn.commit()
    
    print(f"Time taken for index creation: {time.perf_counter() - index_start:.2f} seconds")

    # Close the main thread's database connection
    conn.close()

    # Signal the processor thread to stop
    stop_event.set()

    # Join the processor threads
    for processor_thread in processor_threads:
        processor_thread.join()

    print(f"Total time taken: {time.perf_counter() - start:.2f} seconds")
    print(f"Total runs processed: {NUM_RUNS}")

def main():
    """Run benchmarks with specified parameters."""
    json_size = 5_000
    num_runs = 10_000

    benchmark_run_creation(json_size, num_runs)

if __name__ == "__main__":
    main()