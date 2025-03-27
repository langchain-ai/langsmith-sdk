import asyncio
import random
import time

from langsmith import traceable, Client

async def test_aevaluate_large_dataset_and_concurrency():
    @traceable(run_type="llm")
    async def mock_chat_completion(*, model, messages):
        # Sleep for between .5 and 1.5 seconds each time
        await asyncio.sleep(random.uniform(.5, 1.5))
        # Will return a random equation on the third call
        if len(messages) == 6:
            return {
                "role": "assistant",
                "content": f"y = {random.random()}x + b"
            }
        return {
            "role": "assistant",
            "content": "Still thinking...",
        }

    def simulate_conversation_turn(*, existing, model_response):
        return existing + [
            model_response,
            {
                "role": "human",
                "content": "Think harder!"
            }
        ]

    # Will be traced by default
    async def target(inputs: dict) -> dict:
        messages = [
            {
                "role": "system",
                "content": "Come up with a math equation that solves the puzzle."
            },
            # This dataset has inputs as a dict with a "statement" key
            {"role": "user", "content": inputs["statement"]},
        ]
        res = await mock_chat_completion(
            model="gpt-4o-mini",
            messages=messages
        )
        messages = simulate_conversation_turn(existing=messages, model_response=res)
        res = await mock_chat_completion(
            model="gpt-4o-mini",
            messages=messages
        )
        messages = simulate_conversation_turn(existing=messages, model_response=res)
        res = await mock_chat_completion(
            model="gpt-4o-mini",
            messages=messages
        )

        return { "equation": res }
    @traceable(run_type="llm")
    async def mock_evaluator_chat_completion(*, model, messages):
        await asyncio.sleep(random.uniform(1.5, 2.5))
        return {
            "role": "assistant",
            "content": str(random.random()),
        }

    async def mock_correctness_evaluator(outputs: dict, reference_outputs: dict):
        messages = [
            {
                "role": "system",
                "content": "Assign a score to the following output."
            },
            {
                "role": "user",
                "content": f"""
Reference: {reference_outputs["equation"]}
Actual: {outputs["equation"]}
"""
            },
        ]
        res = await mock_evaluator_chat_completion(
            model="o3-mini",
            messages=messages
        )
        return {
            "key": "correctness",
            "score": float(res["content"]),
            "comment": "The answer was a good attempt, but incorrect."
        }
    client = Client()

    print("Starting experiment!")
    start = time.time()

    experiment_results = await client.aevaluate(
        target,
        # dataset with 9,900 examples
        data="superhuman logic puzzles",
        evaluators=[
            mock_correctness_evaluator,
            # can add multiple evaluators here
        ],
        max_concurrency=100,
    )

    finish_time = time.time()

    print(f"Experiment finished in {finish_time - start} seconds")

    client.flush()

    flush_time = time.time()

    print(f"All runs flushed to LangSmith in {flush_time - finish_time} seconds")