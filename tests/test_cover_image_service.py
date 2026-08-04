from __future__ import annotations

import time

import pytest
import requests

from AniRec.errors import DataError, NetworkError
from AniRec.gui.workers import CoverDownloadWorker, WorkerController
from AniRec.gui_main import create_application
from AniRec.services import CoverImageService


class Response:
    status_code = 200

    def __init__(self, chunks=(b"\xff\xd8\xfffixture-image",), content_type="image/jpeg", length=None):
        self.chunks = chunks
        self.headers = {"Content-Type": content_type}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def iter_content(self, chunk_size):
        yield from self.chunks


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def test_cover_service_requires_https_supported_type_and_size_limit(system_temp_dir):
    service = CoverImageService(
        root_override=system_temp_dir,
        http_get=lambda *_args, **_kwargs: Response(),
    )
    with pytest.raises(DataError, match="HTTPS"):
        service.fetch("http://example.test/cover.jpg")

    wrong_type = CoverImageService(
        root_override=system_temp_dir,
        http_get=lambda *_args, **_kwargs: Response(content_type="text/html"),
    )
    with pytest.raises(DataError, match="image type"):
        wrong_type.fetch("https://example.test/wrong")

    oversized = CoverImageService(
        root_override=system_temp_dir,
        max_bytes=5,
        http_get=lambda *_args, **_kwargs: Response(length=10),
    )
    with pytest.raises(DataError, match="size limit"):
        oversized.fetch("https://example.test/large")


def test_cover_timeout_maps_to_safe_network_error(system_temp_dir):
    def timeout(*_args, **_kwargs):
        raise requests.Timeout("fixture")

    with pytest.raises(NetworkError):
        CoverImageService(root_override=system_temp_dir, http_get=timeout).fetch(
            "https://example.test/cover.jpg"
        )


def test_cover_rejects_corrupt_bytes_even_with_an_image_content_type(system_temp_dir):
    service = CoverImageService(
        root_override=system_temp_dir,
        http_get=lambda *_args, **_kwargs: Response(chunks=(b"not-an-image",)),
    )

    with pytest.raises(DataError, match="invalid image data"):
        service.fetch("https://example.test/corrupt.jpg")

    assert not service.cache_path("https://example.test/corrupt.jpg").exists()


def test_cover_disk_cache_avoids_second_network_request(system_temp_dir):
    calls = []

    def fetch(*_args, **_kwargs):
        calls.append(True)
        return Response(chunks=(b"\xff\xd8\xffone", b"two"))

    service = CoverImageService(root_override=system_temp_dir, http_get=fetch)
    first = service.fetch("https://example.test/cover.jpg")
    second = service.fetch("https://example.test/cover.jpg")

    assert first.data == b"\xff\xd8\xffonetwo"
    assert not first.cache_hit
    assert second.data == first.data
    assert second.cache_hit
    assert calls == [True]
    assert list(first.cache_path.parent.glob("*.tmp")) == []


def test_cover_worker_returns_cached_result_without_blocking_gui(system_temp_dir):
    application = create_application([])
    service = CoverImageService(
        root_override=system_temp_dir,
        http_get=lambda *_args, **_kwargs: Response(),
    )
    controller = WorkerController()
    results = []
    controller.result_ready.connect(lambda _key, value: results.append(value))
    controller.start(
        "cover:fixture",
        CoverDownloadWorker(service, "https://example.test/cover.jpg"),
    )
    wait_until(application, lambda: not controller.active_keys)

    assert results[0].data == b"\xff\xd8\xfffixture-image"
