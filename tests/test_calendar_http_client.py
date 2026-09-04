import requests

import http_client


class FakeSession:
    def __init__(self, responses):
        self.headers = {"User-Agent": "CodeCollectiveBot/test"}
        self._responses = list(responses)
        self.requests = []

    def get(self, url, timeout=None, **kwargs):
        self.requests.append((url, kwargs))
        response = self._responses.pop(0)
        response.url = url
        return response


def make_response(status, body=b"", headers=None):
    response = requests.Response()
    response.status_code = status
    response._content = body
    response._content_consumed = True
    response.headers.update(headers or {})
    response.encoding = "utf-8"
    return response


def test_polite_get_revalidates_cached_body(tmp_path, monkeypatch):
    monkeypatch.setattr(http_client, "HTTP_CACHE_DIR", tmp_path)
    monkeypatch.setattr(http_client, "HTTP_CACHE_ENABLED", True)
    monkeypatch.setattr(http_client, "_last_request_by_host", {})

    url = "https://example.com/events"
    first = make_response(
        200,
        b"fresh event payload",
        {"ETag": '"calendar-v1"', "Content-Type": "text/plain"},
    )
    second = make_response(304)
    session = FakeSession([first, second])

    initial = http_client.polite_get(
        session,
        url,
        respect_robots=False,
        min_interval_seconds=0,
    )
    revalidated = http_client.polite_get(
        session,
        url,
        respect_robots=False,
        min_interval_seconds=0,
    )

    assert initial.content == b"fresh event payload"
    assert revalidated.status_code == 200
    assert revalidated.content == b"fresh event payload"
    assert revalidated.headers["X-CodeCollective-Cache"] == "revalidated"
    assert session.requests[1][1]["headers"]["If-None-Match"] == '"calendar-v1"'
