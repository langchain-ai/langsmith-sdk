import os

print(os.getenv("LANGSMITH_API_KEY")[::5])

dataset_name = "test Kiewan"

from langsmith import Client

client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))

dataset = client.create_dataset(dataset_name=dataset_name, description="A dataset for Q&A tasks")
