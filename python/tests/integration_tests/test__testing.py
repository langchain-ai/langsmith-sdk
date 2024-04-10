import pytest

from langsmith import unit

# @unit
# def test_addition():
#     assert 3 + 4 == 7


# @pytest.fixture
# def some_input():
#     return "Some input"


# @unit
# def test_with_fixture(some_input: str):
#     assert "input" in some_input


# @pytest.fixture
# def expected_output():
#     return "input"


# @unit(output_keys=["result"])
# def test_with_expected_output(some_input: str, expected_output: str):
#     assert expected_output in some_input


# @unit(id=uuid.uuid4())
# def test_multiplication():
#     assert 3 * 4 == 12


# @unit
# def test_openai_says_hello():
#     # Traced code will be included in the test case
#     oai_client = wrap_openai(openai.Client())
#     response = oai_client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user", "content": "Say hello!"},
#         ],
#     )
#     assert "hello" in response.choices[0].message.content.lower()


## Multiple inputs
@unit(output_keys=["expected"])
@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 3),
        (3, 4, 7),
    ],
)
def test_addition_with_multiple_inputs(a: int, b: int, expected: int):
    assert a + b == expected
