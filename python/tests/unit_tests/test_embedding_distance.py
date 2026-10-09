import pytest

pytest.importorskip("numpy")

from langsmith._internal._embedding_distance import EmbeddingDistance  # noqa: E402


@pytest.mark.parametrize(
    "metric,expected",
    [
        ("cosine", 0.0),
        ("euclidean", 5**0.5),
        ("manhattan", 3.0),
        ("chebyshev", 2.0),
        ("hamming", 1.0),
    ],
)
def test_embedding_distance_metrics(metric: str, expected: float) -> None:
    def encoder(texts):
        return [[1.0, 2.0], [2.0, 4.0]]

    result = EmbeddingDistance({"encoder": encoder, "metric": metric}).evaluate(
        "a", "b"
    )
    assert result == pytest.approx(expected, abs=1e-9)
