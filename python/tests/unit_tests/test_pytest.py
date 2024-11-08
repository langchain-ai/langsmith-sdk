import langsmith as ls


@ls.pytest.mark.parametrize("Sample Dataset 3", (lambda x: x))
def test_parametrize(inputs, outputs, reference_outputs) -> list:
    assert inputs == outputs
    return [{"key": "foo", "value": "bar"}]
