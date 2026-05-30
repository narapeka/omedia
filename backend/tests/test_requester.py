from __future__ import annotations

import gzip
import io
import ssl
import threading
import unittest
from email.message import Message
from email.utils import formatdate
from urllib.error import HTTPError, URLError
from urllib.request import Request

from app.infra.http.requester import ProviderRequester, RequesterPolicy


class ProviderRequesterTests(unittest.TestCase):
    def test_rate_limit_spaces_request_starts(self) -> None:
        clock = FakeClock()
        opener = FakeOpener([FakeResponse(b"one"), FakeResponse(b"two")])
        requester = make_requester(rate_limit=5, opener=opener, clock=clock)

        requester.read(Request("https://example.test/one"), timeout_seconds=3)
        requester.read(Request("https://example.test/two"), timeout_seconds=3)

        self.assertEqual(clock.sleeps, [0.2])
        self.assertEqual(opener.timeout_values, [3, 3])

    def test_fractional_rate_limit_spaces_request_starts(self) -> None:
        clock = FakeClock()
        opener = FakeOpener([FakeResponse(), FakeResponse()])
        requester = make_requester(rate_limit=0.5, opener=opener, clock=clock)

        requester.read(Request("https://example.test/one"), timeout_seconds=3)
        requester.read(Request("https://example.test/two"), timeout_seconds=3)

        self.assertEqual(clock.sleeps, [2.0])

    def test_provider_instances_have_independent_pacing(self) -> None:
        clock = FakeClock()
        first = make_requester(rate_limit=1, opener=FakeOpener([FakeResponse()]), clock=clock)
        second = make_requester(rate_limit=1, opener=FakeOpener([FakeResponse()]), clock=clock)

        first.read(Request("https://example.test/one"), timeout_seconds=3)
        second.read(Request("https://example.test/two"), timeout_seconds=3)

        self.assertEqual(clock.sleeps, [])

    def test_concurrency_is_bounded(self) -> None:
        release = threading.Event()
        entered = threading.Event()
        opener = BlockingOpener(release, entered)
        requester = make_requester(rate_limit=100, opener=opener, policy=RequesterPolicy(frozenset(), 0, 1, 2, 1))
        first = threading.Thread(target=lambda: requester.read(Request("https://example.test/one"), timeout_seconds=3))
        second = threading.Thread(target=lambda: requester.read(Request("https://example.test/two"), timeout_seconds=3))

        first.start()
        entered.wait(1)
        second.start()
        self.assertEqual(opener.active, 1)
        self.assertEqual(opener.max_active, 1)

        release.set()
        first.join(1)
        second.join(1)
        self.assertEqual(opener.max_active, 1)

    def test_retries_retryable_status_with_backoff_jitter(self) -> None:
        clock = FakeClock()
        opener = FakeOpener([http_error(500), FakeResponse(b"ok")])
        requester = make_requester(rate_limit=100, opener=opener, clock=clock, jitter=lambda _delay: 0.25)

        body = requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertEqual(body, b"ok")
        self.assertIn(1.25, clock.sleeps)
        self.assertEqual(opener.calls, 2)

    def test_retries_transport_error_with_backoff_jitter(self) -> None:
        clock = FakeClock()
        tls_error = URLError(ssl.SSLError("UNEXPECTED_EOF_WHILE_READING"))
        opener = FakeOpener([tls_error, FakeResponse(b"ok")])
        requester = make_requester(rate_limit=100, opener=opener, clock=clock, jitter=lambda _delay: 0.25)

        body = requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertEqual(body, b"ok")
        self.assertIn(1.25, clock.sleeps)
        self.assertEqual(opener.calls, 2)

    def test_decompresses_gzip_response_by_header(self) -> None:
        compressed = gzip.compress(b'{"ok": true}')
        opener = FakeOpener([FakeResponse(compressed, headers={"Content-Encoding": "gzip"})])
        requester = make_requester(rate_limit=100, opener=opener)

        body = requester.read(Request("https://example.test/gzip"), timeout_seconds=3)

        self.assertEqual(body, b'{"ok": true}')

    def test_decompresses_gzip_response_by_magic_bytes(self) -> None:
        compressed = gzip.compress(b'{"ok": true}')
        opener = FakeOpener([FakeResponse(compressed)])
        requester = make_requester(rate_limit=100, opener=opener)

        body = requester.read(Request("https://example.test/gzip"), timeout_seconds=3)

        self.assertEqual(body, b'{"ok": true}')

    def test_honors_retry_after_seconds(self) -> None:
        clock = FakeClock()
        opener = FakeOpener([http_error(429, retry_after="4"), FakeResponse(b"ok")])
        requester = make_requester(rate_limit=100, opener=opener, clock=clock)

        requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertIn(4.0, clock.sleeps)

    def test_honors_retry_after_http_date(self) -> None:
        clock = FakeClock()
        retry_at = formatdate(usegmt=True)
        opener = FakeOpener([http_error(429, retry_after=retry_at), FakeResponse(b"ok")])
        requester = make_requester(rate_limit=100, opener=opener, clock=clock)

        requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertGreaterEqual(clock.sleeps[0], 0.0)

    def test_does_not_retry_non_retryable_status(self) -> None:
        opener = FakeOpener([http_error(400)])
        requester = make_requester(rate_limit=100, opener=opener)

        with self.assertRaises(HTTPError):
            requester.read(Request("https://example.test/bad"), timeout_seconds=3)

        self.assertEqual(opener.calls, 1)

    def test_reraises_after_retry_exhaustion(self) -> None:
        opener = FakeOpener([http_error(500), http_error(500)])
        requester = make_requester(
            rate_limit=100,
            opener=opener,
            policy=RequesterPolicy(frozenset({500}), 1, 1, 2, 1),
            jitter=lambda _delay: 0,
        )

        with self.assertRaises(HTTPError):
            requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertEqual(opener.calls, 2)

    def test_reraises_transport_error_after_retry_exhaustion(self) -> None:
        opener = FakeOpener([URLError("first"), URLError("second")])
        requester = make_requester(
            rate_limit=100,
            opener=opener,
            policy=RequesterPolicy(frozenset(), 1, 1, 2, 1),
            jitter=lambda _delay: 0,
        )

        with self.assertRaises(URLError):
            requester.read(Request("https://example.test/retry"), timeout_seconds=3)

        self.assertEqual(opener.calls, 2)

    def test_proxy_builds_per_requester_opener(self) -> None:
        requester = ProviderRequester(
            name="proxy-test",
            rate_limit=1,
            proxy="http://127.0.0.1:10809",
            policy=RequesterPolicy(frozenset(), 0, 1, 2, 1),
        )

        self.assertEqual(requester.proxy, "http://127.0.0.1:10809")


def make_requester(
    *,
    rate_limit: float,
    opener,
    clock: "FakeClock | None" = None,
    policy: RequesterPolicy | None = None,
    jitter=None,
):
    clock = clock or FakeClock()
    return ProviderRequester(
        name="test",
        rate_limit=rate_limit,
        policy=policy or RequesterPolicy(frozenset({429, 500, 502, 503, 504}), 3, 1, 10, 2),
        opener=opener,
        clock=clock.now,
        sleeper=clock.sleep,
        jitter=jitter or (lambda _delay: 0),
    )


def http_error(code: int, *, retry_after: str | None = None) -> HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError("https://example.test", code, "error", headers, io.BytesIO(b"error"))


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class FakeResponse:
    def __init__(self, body: bytes = b"{}", headers: dict[str, str] | None = None):
        self.body = body
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self.body


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.timeout_values: list[float] = []

    def open(self, _request, *, timeout):
        self.calls += 1
        self.timeout_values.append(timeout)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class BlockingOpener:
    def __init__(self, release: threading.Event, entered: threading.Event):
        self.release = release
        self.entered = entered
        self.active = 0
        self.max_active = 0

    def open(self, _request, *, timeout):
        return BlockingResponse(self)


class BlockingResponse:
    def __init__(self, opener: BlockingOpener):
        self.opener = opener

    def __enter__(self):
        self.opener.active += 1
        self.opener.max_active = max(self.opener.max_active, self.opener.active)
        self.opener.entered.set()
        self.opener.release.wait(1)
        return self

    def __exit__(self, *_args):
        self.opener.active -= 1
        return None

    def read(self) -> bytes:
        return b"{}"


if __name__ == "__main__":
    unittest.main()
