import os
from langsmith import Client
import json

trace_ids = set([
    "1efb1bff-10d5-6da0-98e2-1fca189219e1",
    "1efb1bfd-1be8-653b-8edc-0f4c94f2f6b3",
    "1efb1bfb-4e07-6398-b544-bd111c9a6996",
    "1efb1bf8-42d4-648a-81be-b7ba3342459e",
    "1efb1bf7-6a50-6431-9eb8-6ae7b2198b38",
    "1efb1bf5-64fd-6a08-90cb-f5c225bf6dd4",
    "1efb1bf3-4d7c-6e2a-97f3-02bb3afb6047",
    "1efb1bf2-0fda-6b60-8e4a-a10d684ac89a",
    "1efb1bf0-1b5a-673f-a1e3-a6f6a4f20e6a",
    "1efb1b8f-4b60-6140-a975-7ea154e8fc81"


])

os.environ["LANGCHAIN_API_KEY"] = "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"

client = Client()
results = []
for i, trace_id in enumerate(trace_ids):
    results = client.list_runs(
        project_name='chat-langchain-langgraph-cloud',
        trace_id=trace_id,
        select=["inputs", "outputs", "run_type", "dotted_order", "trace_id"],
    )

    results = list(results)
    results.sort(key=lambda x: x.dotted_order)


    with open(f'inputs_{i}.jsonl', 'w') as inputs_file, open(f'outputs_{i}.jsonl', 'w') as outputs_file:
        for res in results:
            json.dump(res.inputs, inputs_file)
            inputs_file.write('\n')
            json.dump(res.outputs, outputs_file)
            outputs_file.write('\n')



    



