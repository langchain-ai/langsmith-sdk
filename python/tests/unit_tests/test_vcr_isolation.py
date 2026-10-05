import threading

import httpx
import pytest
import vcr
import vcr.patch


@pytest.fixture(autouse=True)
def vcr_fixture():
    yield


@pytest.mark.parametrize("method", ["handle_request", "handle_async_request"])
def test_httpx_cassette_survives_background_passthrough(tmp_path, method):
    entered = threading.Event()
    release = threading.Event()

    def passthrough():
        with vcr.patch.force_reset():
            entered.set()
            assert release.wait(10)

    transport = (
        httpx.HTTPTransport if method == "handle_request" else httpx.AsyncHTTPTransport
    )
    recorder = vcr.VCR(record_mode="none")
    with recorder.use_cassette(str(tmp_path / "first.yaml")):
        worker = threading.Thread(target=passthrough)
        worker.start()
        assert entered.wait(10)

    try:
        with recorder.use_cassette(str(tmp_path / "second.yaml")):
            current = getattr(transport, method)
            release.set()
            worker.join(10)
            assert not worker.is_alive()
            assert getattr(transport, method) is current
    finally:
        release.set()
        worker.join(10)
