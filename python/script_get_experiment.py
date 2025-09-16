# from langsmith import Client
# import pprint
# import os 
# os.environ["LANGSMITH_API_KEY"] = "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"
# os.environ["LANGSMITH_TRACING"] = "true"
# os.environ["LANGSMITH_ENDPOINT"] = "http://localhost:1980/api/v1"


# client = Client()

# # experiment = client.get_experiment(dataset_id="123", experiment_id="456")
# examples = client.get_experiment(dataset_id="f01ffa03-5a25-4163-a6a3-66b6af72378f", session_ids=["037ae90f-f297-4926-b93c-37d8abf6899f"])

# # examples = client.get_test_results(project_id="037ae90f-f297-4926-b93c-37d8abf6899f")

# for i, example in enumerate(examples):
#     if i == 1149: 
#         pprint.pprint(i)
#         pprint.pprint(example)
#         breakpoint()
#         pprint.pprint(example.keys())




from langsmith import Client
import pprint
import os 
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"


client = Client()

# experiment = client.get_experiment(dataset_id="123", experiment_id="456")
examples = client.get_experiment(dataset_id="18186635-ee37-476b-94df-10693ed73cfe", session_ids=["40a436a8-28a2-4126-8f4d-78d5ff074930"])

# examples = client.get_test_results(project_id="037ae90f-f297-4926-b93c-37d8abf6899f")

for i, example in enumerate(examples):
    print(example)
    if i == 1: 
        pprint.pprint(i)
        pprint.pprint(example)
        breakpoint()
        pprint.pprint(example.keys())







