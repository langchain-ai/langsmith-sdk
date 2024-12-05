import orjson
import zlib
import uuid
import zstandard as zstd
import time
import io
from typing import List, Dict, Tuple, Any
from requests_toolbelt.multipart import encoder as rqtb_multipart


class MultipartPartsAndContext:
    def __init__(self, parts: List[Tuple[str, Tuple[None, bytes, str, Dict[str, str]]]], 
                 context: str):
        self.parts = parts
        self.context = context

class SerializedRunOperation:
    def __init__(self, data: Dict[str, Any]):
        self.operation = data["operation"]
        self.id = data["id"]
        self._none = orjson.dumps(data)
        self.inputs = orjson.dumps(data.get("inputs")) if "inputs" in data else None
        self.outputs = orjson.dumps(data.get("outputs")) if "outputs" in data else None
        self.events = orjson.dumps(data.get("events")) if "events" in data else None
        self.trace_id = data.get("trace_id")
        self.attachments = {}  # Not implemented for multipart experiments


def load_jsonl(filepath: str) -> List[dict]:
    """Load JSONL file and return list of JSON objects."""
    with open(filepath, 'rb') as f:
        return [orjson.loads(line) for line in f]


def measure_compression(data: bytes, compress_func) -> Tuple[
    float, float, float, float]:
    """Measure compression ratio and time."""
    start_time = time.perf_counter()
    compressed = compress_func(data)
    end_time = time.perf_counter()

    original_size = len(data)
    compressed_size = len(compressed)
    compression_ratio = original_size / compressed_size
    time_taken = end_time - start_time

    return compression_ratio, time_taken, compressed_size, original_size


class CompressionExperiment:
    def __init__(self):
        # Initialize compressors
        self.zstd_compressor = zstd.ZstdCompressor(level=3)

    def compress_zlib(self, data: bytes) -> bytes:
        return zlib.compress(data)

    def compress_zstd(self, data: bytes) -> bytes:
        return self.zstd_compressor.compress(data)

    def run_separate_files_experiment(self, inputs: List[dict],
                                      outputs: List[dict]) -> Dict:
        """Experiment 1: Compress input and output files separately."""
        results = {}

        # Convert to bytes using orjson
        inputs_bytes = b'\n'.join(orjson.dumps(x) for x in inputs)
        outputs_bytes = b'\n'.join(orjson.dumps(x) for x in outputs)

        # Test zlib
        inputs_ratio, inputs_time, inputs_size, inputs_original = measure_compression(
            inputs_bytes, self.compress_zlib)
        outputs_ratio, outputs_time, outputs_size, outputs_original = measure_compression(
            outputs_bytes, self.compress_zlib)

        results['zlib'] = {
            'inputs': {
                'ratio': inputs_ratio,
                'time': inputs_time,
                'size': inputs_size,
                'original_size': inputs_original
            },
            'outputs': {
                'ratio': outputs_ratio,
                'time': outputs_time,
                'size': outputs_size,
                'original_size': outputs_original
            },
            'total_size': inputs_size + outputs_size,
            'total_original_size': inputs_original + outputs_original,
            'total_time': inputs_time + outputs_time
        }

        # Test zstd
        inputs_ratio, inputs_time, inputs_size, inputs_original = measure_compression(
            inputs_bytes, self.compress_zstd)
        outputs_ratio, outputs_time, outputs_size, outputs_original = measure_compression(
            outputs_bytes, self.compress_zstd)

        results['zstd'] = {
            'inputs': {
                'ratio': inputs_ratio,
                'time': inputs_time,
                'size': inputs_size,
                'original_size': inputs_original
            },
            'outputs': {
                'ratio': outputs_ratio,
                'time': outputs_time,
                'size': outputs_size,
                'original_size': outputs_original
            },
            'total_size': inputs_size + outputs_size,
            'total_original_size': inputs_original + outputs_original,
            'total_time': inputs_time + outputs_time
        }

        return results

    def run_combined_files_experiment(self, inputs: List[dict],
                                      outputs: List[dict]) -> Dict:
        """Experiment 2: Compress input and output files together."""
        results = {}

        # Combine and convert to bytes using orjson
        combined = []
        for i, o in zip(inputs, outputs):
            combined.extend([i, o])
        combined_bytes = b'\n'.join(orjson.dumps(x) for x in combined)

        # Test both compression algorithms
        for name, compress_func in [('zlib', self.compress_zlib),
                                    ('zstd', self.compress_zstd)]:
            ratio, time_taken, size, original_size = measure_compression(combined_bytes,
                                                                         compress_func)
            results[name] = {
                'ratio': ratio,
                'time': time_taken,
                'size': size,
                'original_size': original_size
            }

        return results

    def run_separate_objects_experiment(self, inputs: List[dict],
                                        outputs: List[dict]) -> Dict:
        """Experiment 3: Compress each JSON object separately."""
        results = {'zlib': {'inputs': [], 'outputs': []},
                   'zstd': {'inputs': [], 'outputs': []}}

        # Process inputs
        for obj in inputs:
            obj_bytes = orjson.dumps(obj)
            for name, compress_func in [('zlib', self.compress_zlib),
                                        ('zstd', self.compress_zstd)]:
                ratio, time_taken, size, original_size = measure_compression(obj_bytes,
                                                                             compress_func)
                results[name]['inputs'].append({
                    'ratio': ratio,
                    'time': time_taken,
                    'size': size,
                    'original_size': original_size
                })

        # Process outputs
        for obj in outputs:
            obj_bytes = orjson.dumps(obj)
            for name, compress_func in [('zlib', self.compress_zlib),
                                        ('zstd', self.compress_zstd)]:
                ratio, time_taken, size, original_size = measure_compression(obj_bytes,
                                                                             compress_func)
                results[name]['outputs'].append({
                    'ratio': ratio,
                    'time': time_taken,
                    'size': size,
                    'original_size': original_size
                })

        # Calculate totals for each compressor
        for compressor in ['zlib', 'zstd']:
            # Calculate inputs totals
            inputs_total_size = sum(m['size'] for m in results[compressor]['inputs'])
            inputs_total_original = sum(
                m['original_size'] for m in results[compressor]['inputs'])
            inputs_total_time = sum(m['time'] for m in results[compressor]['inputs'])

            # Calculate outputs totals
            outputs_total_size = sum(m['size'] for m in results[compressor]['outputs'])
            outputs_total_original = sum(
                m['original_size'] for m in results[compressor]['outputs'])
            outputs_total_time = sum(m['time'] for m in results[compressor]['outputs'])

            # Store the results
            results[compressor]['summary'] = {
                'inputs': {
                    'original_size': inputs_total_original,
                    'size': inputs_total_size,
                    'ratio': inputs_total_original / inputs_total_size if inputs_total_size > 0 else 0,
                    'time': inputs_total_time
                },
                'outputs': {
                    'original_size': outputs_total_original,
                    'size': outputs_total_size,
                    'ratio': outputs_total_original / outputs_total_size if outputs_total_size > 0 else 0,
                    'time': outputs_total_time
                },
                'total': {
                    'original_size': inputs_total_original + outputs_total_original,
                    'size': inputs_total_size + outputs_total_size,
                    'ratio': (inputs_total_original + outputs_total_original) /
                             (inputs_total_size + outputs_total_size) if (
                                                                                     inputs_total_size + outputs_total_size) > 0 else 0,
                    'time': inputs_total_time + outputs_total_time
                }
            }

        return results


    def run_streaming_experiment(self, inputs: List[dict], outputs: List[dict]) -> Dict:
        """Experiment 4: Compress combined inputs and outputs using streaming."""
        results = {}

        # Combine inputs and outputs alternating
        combined = []
        for i, o in zip(inputs, outputs):
            combined.extend([i, o])

        # Test zlib streaming
        start_time = time.perf_counter()

        # Create a BytesIO buffer for zlib
        import io
        zlib_buffer = io.BytesIO()
        zlib_compressor = zlib.compressobj()

        original_size = 0
        # Stream each object
        for obj in combined:
            data = orjson.dumps(obj) + b'\n'
            original_size += len(data)
            compressed = zlib_compressor.compress(data)
            if compressed:
                zlib_buffer.write(compressed)

        # Flush any remaining compressed data
        remaining = zlib_compressor.flush()
        if remaining:
            zlib_buffer.write(remaining)

        compressed_size = len(zlib_buffer.getvalue())
        end_time = time.perf_counter()

        results['zlib'] = {
            'original_size': original_size,
            'size': compressed_size,
            'ratio': original_size / compressed_size if compressed_size > 0 else 0,
            'time': end_time - start_time
        }

        # Test zstd streaming
        start_time = time.perf_counter()

        compressor = zstd.ZstdCompressor(level=3)
        zstd_buffer = io.BytesIO()
        with compressor.stream_writer(zstd_buffer) as compressor_writer:
            original_size = 0
            for obj in combined:
                data = orjson.dumps(obj) + b'\n'
                original_size += len(data)
                compressor_writer.write(data)
            compressed_size = len(zstd_buffer.getvalue())
        end_time = time.perf_counter()

        results['zstd'] = {
            'original_size': original_size,
            'size': compressed_size,
            'ratio': original_size / compressed_size if compressed_size > 0 else 0,
            'time': end_time - start_time
        }

        return results

    def run_multipart_streaming_experiment(self, run_ops_files: List[str]) -> Dict:
        """
        Experiment 5: Stream compress multipart forms from multiple run operation files.
        Compresses operations in round-robin fashion across traces.
        """
        start_time = time.perf_counter()
        
        # Create a compressor and buffer
        compressor = zstd.ZstdCompressor(level=3)
        buffer = io.BytesIO()
        
        # Load all files and prepare iterators
        file_handles = []
        file_iterators = []
        for filepath in run_ops_files:
            fh = open(filepath, 'rb')
            file_handles.append(fh)
            file_iterators.append(iter(fh))
        
        original_size = 0
        with compressor.stream_writer(buffer) as compressor_writer:
            while file_iterators:
                # Round robin through files
                for i in range(len(file_iterators)-1, -1, -1):
                    try:
                        # Read next line and parse run operation
                        line = next(file_iterators[i])
                        run_op = SerializedRunOperation(orjson.loads(line)) 
                        # Convert to multipart form
                        multipart_data = serialize_run_operation_to_multipart(run_op)

                        # Compress
                        original_size += len(multipart_data)
                        compressor_writer.write(multipart_data)
                        
                    except StopIteration:
                        # Remove exhausted iterators and close files
                        file_handles[i].close()
                        file_handles.pop(i)
                        file_iterators.pop(i)
        
            compressed_size = len(buffer.getvalue())
        end_time = time.perf_counter()
        
        return {
            'zstd': {
                'original_size': original_size,
                'size': compressed_size,
                'ratio': original_size / compressed_size if compressed_size > 0 else 0,
                'time': end_time - start_time,
                'files_processed': len(run_ops_files)
            }
        }

def serialize_run_operation_to_multipart(op: SerializedRunOperation) -> bytes:
    """Convert a run operation to multipart form data."""
    BOUNDARY = uuid.uuid4().hex
    acc_parts = []
    
    # Add main object
    acc_parts.append(
        (f"{op.operation}.{op.id}",
         (None, op._none, "application/json", {"Content-Length": str(len(op._none))}))
    )
    
    # Add parts
    for key, value in [("inputs", op.inputs), ("outputs", op.outputs), ("events", op.events)]:
        if value is not None:
            acc_parts.append(
                (f"{op.operation}.{op.id}.{key}",
                 (None, value, "application/json", {"Content-Length": str(len(value))}))
            )
    
    # Create multipart form
    mp_encoder = rqtb_multipart.MultipartEncoder(fields=acc_parts, boundary=BOUNDARY)
    if mp_encoder.len <= 20_000_000:  # ~20 MB
        return mp_encoder.to_string()
    else:
        return mp_encoder

def load_multiple_jsonl(base_filepath: str, num_files: int) -> List[List[dict]]:
        """Load multiple JSONL files and return list of JSON objects for each file."""
        import os
        all_files = []
        folder_path = f"./{base_filepath}"
        
        # Get all jsonl files in the directory
        jsonl_files = [f for f in os.listdir(folder_path) if f.endswith('.jsonl')]
        
        for filename in jsonl_files:
            filepath = os.path.join(folder_path, filename)
            with open(filepath, 'rb') as f:
                all_files.append([orjson.loads(line) for line in f])
        return all_files

def format_size(size: int) -> str:
    """Format size in bytes to a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def print_results(experiment_results: Dict):
    """Pretty print the results of all experiments."""
    print("\n=== Experiment 1: Separate Files ===")
    for compressor in ['zlib', 'zstd']:
        print(f"\n{compressor.upper()}:")
        results = experiment_results['separate'][compressor]
        print("Inputs:")
        print(f"  Original Size: {format_size(results['inputs']['original_size'])}")
        print(f"  Compressed Size: {format_size(results['inputs']['size'])}")
        print(f"  Ratio: {results['inputs']['ratio']:.3f}")
        print(f"  Time: {results['inputs']['time'] * 1000:.2f}ms")

        print("Outputs:")
        print(f"  Original Size: {format_size(results['outputs']['original_size'])}")
        print(f"  Compressed Size: {format_size(results['outputs']['size'])}")
        print(f"  Ratio: {results['outputs']['ratio']:.3f}")
        print(f"  Time: {results['outputs']['time'] * 1000:.2f}ms")

        print("Total:")
        print(f"  Original Size: {format_size(results['total_original_size'])}")
        print(f"  Compressed Size: {format_size(results['total_size'])}")
        print(
            f"  Overall Ratio: {results['total_size'] / results['total_original_size']:.3f}")
        print(f"  Total Time: {results['total_time'] * 1000:.2f}ms")

    print("\n=== Experiment 2: Combined Files ===")
    for compressor in ['zlib', 'zstd']:
        print(f"\n{compressor.upper()}:")
        results = experiment_results['combined'][compressor]
        print(f"Original Size: {format_size(results['original_size'])}")
        print(f"Compressed Size: {format_size(results['size'])}")
        print(f"Ratio: {results['ratio']:.3f}")
        print(f"Time: {results['time'] * 1000:.2f}ms")

    print("\n=== Experiment 3: Separate Objects ===")
    for compressor in ['zlib', 'zstd']:
        print(f"\n{compressor.upper()}:")
        summary = experiment_results['separate_objects'][compressor]['summary']

        # Print inputs
        print("Inputs:")
        print(f"  Original Size: {format_size(summary['inputs']['original_size'])}")
        print(f"  Compressed Size: {format_size(summary['inputs']['size'])}")
        print(f"  Ratio: {summary['inputs']['ratio']:.3f}")
        print(f"  Time: {summary['inputs']['time'] * 1000:.2f}ms")

        # Print outputs
        print("Outputs:")
        print(
            f"  Original Size: {format_size(summary['outputs']['original_size'])}")
        print(f"  Compressed Size: {format_size(summary['outputs']['size'])}")
        print(f"  Ratio: {summary['outputs']['ratio']:.3f}")
        print(f"  Time: {summary['outputs']['time'] * 1000:.2f}ms")

        # Print totals
        print("Total:")
        print(f"  Original Size: {format_size(summary['total']['original_size'])}")
        print(f"  Compressed Size: {format_size(summary['total']['size'])}")
        print(f"  Overall Ratio: {summary['total']['ratio']:.3f}")
        print(f"  Total Time: {summary['total']['time'] * 1000:.2f}ms")

    print("\n=== Experiment 4: Streaming Compression ===")
    for compressor in ['zlib', 'zstd']:
        print(f"\n{compressor.upper()}:")
        results = experiment_results['streaming'][compressor]
        print(f"Original Size: {format_size(results['original_size'])}")
        print(f"Compressed Size: {format_size(results['size'])}")
        print(f"Ratio: {results['ratio']:.3f}")
        print(f"Time: {results['time']*1000:.2f}ms")

    print("\n=== Experiment 5: Multipart Form Streaming Compression ===")
    print("\nZSTD:")
    results = experiment_results['multipart']['zstd']
    print(f"Original Size: {format_size(results['original_size'])}")
    print(f"Compressed Size: {format_size(results['size'])}")
    print(f"Ratio: {results['ratio']:.3f}")
    print(f"Time: {results['time']*1000:.2f}ms")
    print(f"Files Processed: {results['files_processed']}")


def main():
    # Load data
    inputs = load_jsonl('inputs.jsonl')
    outputs = load_jsonl('outputs.jsonl')

    import glob
    run_ops_files = glob.glob('data/run_ops_*.jsonl')

    # Initialize and run experiments
    experiment = CompressionExperiment()

    results = {
        'separate': experiment.run_separate_files_experiment(inputs, outputs),
        'combined': experiment.run_combined_files_experiment(inputs, outputs),
        'separate_objects': experiment.run_separate_objects_experiment(inputs, outputs),
        'streaming': experiment.run_streaming_experiment(inputs, outputs),
        'multipart': experiment.run_multipart_streaming_experiment(run_ops_files)
    }

    # Print results
    print_results(results)


if __name__ == "__main__":
    main()