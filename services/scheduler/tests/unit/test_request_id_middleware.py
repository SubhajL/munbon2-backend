"""RequestIDMiddleware bounds inbound X-Request-ID (PR 4.4a-1).

A request id is pinned into approval evidence and echoed into a response
header, so an unsafe inbound value (oversized, control chars, a trailing
newline) must be replaced with a fresh uuid4.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.middleware.request_id import RequestIDMiddleware, _SAFE_REQUEST_ID


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/x")
    async def _x(request: Request):
        return {"rid": request.state.request_id}

    return app


def test_safe_inbound_request_id_is_preserved():
    client = TestClient(_app())
    response = client.get("/x", headers={"X-Request-ID": "safe-id_1.2-3"})
    assert response.json()["rid"] == "safe-id_1.2-3"
    assert response.headers["X-Request-ID"] == "safe-id_1.2-3"


def test_oversized_inbound_request_id_is_replaced():
    client = TestClient(_app())
    response = client.get("/x", headers={"X-Request-ID": "a" * 200})
    assert response.json()["rid"] != "a" * 200  # replaced with a fresh uuid4


def test_trailing_newline_request_id_is_rejected_by_fullmatch():
    # `$` matches just before a final newline, so the old `.match` accepted
    # "safe-id\n"; `.fullmatch` (now used by the middleware) rejects it.
    assert _SAFE_REQUEST_ID.match("safe-id\n") is not None
    assert _SAFE_REQUEST_ID.fullmatch("safe-id\n") is None
    assert _SAFE_REQUEST_ID.fullmatch("safe-id") is not None
