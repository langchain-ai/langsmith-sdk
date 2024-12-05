from langsmith import Client
import orjson
import os

trace_ids = {"1efb1bff-10d5-6da0-98e2-1fca189219e1",
             "1efb1bfd-1be8-653b-8edc-0f4c94f2f6b3",
             "1efb1bfb-4e07-6398-b544-bd111c9a6996",
             "1efb1bf8-42d4-648a-81be-b7ba3342459e",
             "1efb1bf7-6a50-6431-9eb8-6ae7b2198b38",
             "1efb1bf5-64fd-6a08-90cb-f5c225bf6dd4",
             "1efb1bf3-4d7c-6e2a-97f3-02bb3afb6047",
             "1efb1bf2-0fda-6b60-8e4a-a10d684ac89a",
             "1efb1bf0-1b5a-673f-a1e3-a6f6a4f20e6a",
             "1efb1b8f-4b60-6140-a975-7ea154e8fc81",
             "1efb27a4-5264-6908-9ab5-23fc3c60ae2d"}

# trace_ids = {"1efb27a4-5264-6908-9ab5-23fc3c60ae2d"}

def produce_inputs_outputs_jsonl_files():
    client = Client()
    for i, trace_id in enumerate(trace_ids):
        results = client.list_runs(
            project_name='chat-langchain-langgraph-cloud',
            trace_id=trace_id,
        )
        results = list(results)
        results.sort(key=lambda x: x.dotted_order)
        with open(f'inputs_{i}.jsonl', 'wb') as inputs_file, open(f'outputs_{i}.jsonl', 'wb') as outputs_file:
            for res in results:
                inputs_file.write(orjson.dumps(res.inputs))
                inputs_file.write('\n')
                outputs_file.write(orjson.dumps(res.outputs))
                outputs_file.write('\n')

def produce_run_ops_jsonl_files():
    client = Client()
    for trace_id in trace_ids:
        results = client.list_runs(
            project_name='chat-langchain-langgraph-cloud',
            trace_id=trace_id,
        )
        results = list(results)
        results.sort(key=lambda x: x.dotted_order)
        with open(f'data/run_ops_{trace_id}.jsonl', 'wb') as run_ops_file:
            for run in results:
                run_dict = dict(run)
                post = {
                    "operation": "post",
                    "id": run_dict["id"],
                    "name": run_dict["name"],
                    "start_time": run_dict["start_time"],
                    "serialized": run_dict["serialized"],
                    "events": run_dict["events"],
                    "inputs": run_dict["inputs"],
                    "run_type": run_dict["run_type"],
                    "extra": run_dict["extra"],
                    "tags": run_dict["tags"],
                    "trace_id": run_dict["trace_id"],
                    "dotted_order": run_dict["dotted_order"],
                }
                run_ops_file.write(orjson.dumps(post))
                run_ops_file.write(b'\n')
                patch = {
                    "operation": "patch",
                    "id": run_dict["id"],
                    "name": run_dict["name"],
                    "end_time": run_dict["end_time"],
                    "error": run_dict["error"],
                    "outputs": run_dict["outputs"],
                }
                run_ops_file.write(orjson.dumps(patch))
                run_ops_file.write(b'\n')

if __name__ == "__main__":
    produce_run_ops_jsonl_files()