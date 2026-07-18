import re
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# An inbound X-Request-ID is accepted only if it matches this bounded, safe
# pattern; anything else (oversized, control chars, injection payloads) is
# replaced with a fresh uuid4 so the id can be safely logged and pinned into
# approval evidence.
# fullmatch (below) is used rather than match so a trailing newline cannot slip
# through — `$` matches just before a final "\n", which would let "safe-id\n" be
# echoed into the response header.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a bounded, safe request id to each request."""

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get("X-Request-ID")
        if inbound is not None and _SAFE_REQUEST_ID.fullmatch(inbound):
            request_id = inbound
        else:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
