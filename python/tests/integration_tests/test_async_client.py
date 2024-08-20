import asyncio
import uuid

import pytest
from pydantic import BaseModel

from langsmith.async_client import AsyncClient


@pytest.mark.asyncio
async def test_indexed_datasets():
    class InputsSchema(BaseModel):
        name: str
        age: int

    async with AsyncClient() as client:
        # Create a new dataset
        dataset = await client.create_dataset(
            "test_dataset_for_integration_tests_" + uuid.uuid4().hex,
            inputs_schema_definition=InputsSchema.model_json_schema(),
        )

        example = await client.create_example(
            inputs={"name": "Alice", "age": 30},
            outputs={"hi": "hello"},
            dataset_id=dataset.id,
        )

        await client.index_dataset(dataset_id=dataset.id)
        for _ in range(10):
            examples = await client.similar_examples(
                {"name": "Bob", "age": 22}, dataset_id=dataset.id, limit=5
            )

            if len(examples) == 1:
                break

            await asyncio.sleep(1)

        assert len(examples) == 1
        assert examples[0].id == example.id
