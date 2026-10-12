from typing import Literal
from unittest import mock

import pytest

from langsmith import expect
from langsmith._expect import ls_client
from langsmith._internal._embedding_distance import EmbeddingConfig, EmbeddingDistance


def _is_none(x: object) -> bool:
    return x is None


@mock.patch.object(ls_client, "Client", autospec=True)
def test_expect_explicit_none(mock_client: mock.Mock) -> None:
    expect(None).against(_is_none)
    expect(None).to_be_none()
    expect.score(1).to_equal(1)
    expect.score(1).to_be_less_than(2)
    expect.score(1).to_be_greater_than(0)
    expect.score(1).to_be_between(0, 2)
    expect.score(1).to_be_approximately(1, 2)
    expect({1, 2}).to_contain(1)


@pytest.mark.parametrize(
    "metric, expected",
    [
        ("cosine", 1 - 9 / (5 * 18**0.5)),
        ("euclidean", 5.0),
        ("manhattan", 7.0),
        ("chebyshev", 4.0),
        ("hamming", 0.5),
    ],
)
@mock.patch.object(ls_client, "Client", autospec=True)
def test_embedding_distance(
    mock_client: mock.Mock,
    metric: Literal["cosine", "euclidean", "manhattan", "chebyshev", "hamming"],
    expected: float,
) -> None:
    config: EmbeddingConfig = {
        "metric": metric,
        "encoder": lambda texts: [[3.0, 4.0, 0.0, 0.0], [3.0, 0.0, 0.0, 3.0]],
    }
    distance = EmbeddingDistance(config).evaluate("a", "b")
    assert isinstance(distance, float)
    assert distance == pytest.approx(expected)
    expect.embedding_distance("a", "b", config=config).to_be_approximately(expected)
