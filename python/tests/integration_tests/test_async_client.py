import asyncio
import datetime
import uuid

import pytest
from pydantic import BaseModel

from langsmith import utils as ls_utils
from langsmith.async_client import AsyncClient
from langsmith.schemas import DataType, Run


@pytest.mark.asyncio
async def test_indexed_datasets():
    class InputsSchema(BaseModel):
        name: str  # type: ignore[annotation-unchecked]
        age: int  # type: ignore[annotation-unchecked]

    async with AsyncClient() as client:
        # Create a new dataset
        try:
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

            async def check_similar_examples():
                examples = await client.similar_examples(
                    {"name": "Alice", "age": 30}, dataset_id=dataset.id, limit=1
                )
                return len(examples) == 1

            await wait_for(check_similar_examples, timeout=20)
            examples = await client.similar_examples(
                {"name": "Alice", "age": 30}, dataset_id=dataset.id, limit=1
            )
            assert examples[0].id == example.id
        finally:
            await client.delete_dataset(dataset_id=dataset.id)


# Helper function to wait for a condition
async def wait_for(condition, timeout=10):
    start_time = asyncio.get_event_loop().time()
    while True:
        try:
            if await condition():
                return
        except Exception:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("Condition not met within the timeout period")
            await asyncio.sleep(0.1)


@pytest.fixture
async def async_client():
    client = AsyncClient()
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_create_run(async_client: AsyncClient):
    project_name = "__test_create_run" + uuid.uuid4().hex[:8]
    run_id = uuid.uuid4()

    await async_client.create_run(
        name="test_run",
        inputs={"input": "hello"},
        run_type="llm",
        project_name=project_name,
        id=run_id,
        start_time=datetime.datetime.now(datetime.timezone.utc),
    )

    async def check_run():
        try:
            run = await async_client.read_run(run_id)
            return run.name == "test_run"
        except ls_utils.LangSmithError:
            return False

    await wait_for(check_run)
    run = await async_client.read_run(run_id)
    assert run.name == "test_run"
    assert run.inputs == {"input": "hello"}


@pytest.mark.asyncio
async def test_list_runs(async_client: AsyncClient):
    project_name = "__test_list_runs"
    run_ids = [uuid.uuid4() for _ in range(3)]
    meta_uid = str(uuid.uuid4())

    for i, run_id in enumerate(run_ids):
        await async_client.create_run(
            name=f"test_run_{i}",
            inputs={"input": f"hello_{i}"},
            run_type="llm",
            project_name=project_name,
            id=run_id,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            end_time=datetime.datetime.now(datetime.timezone.utc),
            extra={"metadata": {"uid": meta_uid}},
        )

    filter_ = f'and(eq(metadata_key, "uid"), eq(metadata_value, "{meta_uid}"))'

    async def check_runs():
        runs = [
            run
            async for run in async_client.list_runs(
                project_name=project_name, filter=filter_
            )
        ]
        return len(runs) == 3

    await wait_for(check_runs)

    runs = [
        run
        async for run in async_client.list_runs(
            project_name=project_name, filter=filter_
        )
    ]
    assert len(runs) == 3
    assert all(isinstance(run, Run) for run in runs)


@pytest.mark.asyncio
async def test_create_dataset(async_client: AsyncClient):
    dataset_name = "__test_create_dataset" + uuid.uuid4().hex[:8]

    dataset = await async_client.create_dataset(dataset_name, data_type=DataType.kv)

    assert dataset.name == dataset_name
    assert dataset.data_type == DataType.kv

    await async_client.delete_dataset(dataset_id=dataset.id)


@pytest.mark.asyncio
async def test_create_example(async_client: AsyncClient):
    dataset_name = "__test_create_example" + uuid.uuid4().hex[:8]
    dataset = await async_client.create_dataset(dataset_name)

    example = await async_client.create_example(
        inputs={"input": "hello"}, outputs={"output": "world"}, dataset_id=dataset.id
    )

    assert example.inputs == {"input": "hello"}
    assert example.outputs == {"output": "world"}

    await async_client.delete_dataset(dataset_id=dataset.id)


@pytest.mark.asyncio
async def test_list_examples(async_client: AsyncClient):
    dataset_name = "__test_list_examples" + uuid.uuid4().hex[:8]
    dataset = await async_client.create_dataset(dataset_name)

    for i in range(3):
        await async_client.create_example(
            inputs={"input": f"hello_{i}"},
            outputs={"output": f"world_{i}"},
            dataset_id=dataset.id,
        )

    examples = [
        example async for example in async_client.list_examples(dataset_id=dataset.id)
    ]
    assert len(examples) == 3

    await async_client.delete_dataset(dataset_id=dataset.id)


@pytest.mark.asyncio
async def test_create_feedback(async_client: AsyncClient):
    project_name = "__test_create_feedback" + uuid.uuid4().hex[:8]
    run_id = uuid.uuid4()

    await async_client.create_run(
        name="test_run",
        inputs={"input": "hello"},
        run_type="llm",
        project_name=project_name,
        id=run_id,
        start_time=datetime.datetime.now(datetime.timezone.utc),
    )

    feedback = await async_client.create_feedback(
        run_id=run_id,
        key="test_key",
        score=0.9,
        value="test_value",
        comment="test_comment",
    )

    assert feedback.run_id == run_id
    assert feedback.key == "test_key"
    assert feedback.score == 0.9
    assert feedback.value == "test_value"
    assert feedback.comment == "test_comment"


@pytest.mark.asyncio
async def test_list_feedback(async_client: AsyncClient):
    project_name = "__test_list_feedback"
    run_id = uuid.uuid4()

    await async_client.create_run(
        name="test_run",
        inputs={"input": "hello"},
        run_type="llm",
        project_name=project_name,
        id=run_id,
        start_time=datetime.datetime.now(datetime.timezone.utc),
    )

    for i in range(3):
        await async_client.create_feedback(
            run_id=run_id,
            key=f"test_key_{i}",
            score=0.9,
            value=f"test_value_{i}",
            comment=f"test_comment_{i}",
        )

    async def check_feedbacks():
        feedbacks = [
            feedback async for feedback in async_client.list_feedback(run_ids=[run_id])
        ]
        return len(feedbacks) == 3

    await wait_for(check_feedbacks, timeout=10)
