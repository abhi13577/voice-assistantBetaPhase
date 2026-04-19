import uuid
import hmac
from fastapi import Request
from starlette.responses import JSONResponse

from app.core.config import REQUIRE_API_KEY, API_KEY


async def request_id_middleware(request: Request, call_next):

    request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    # Simple service-to-service auth guard.
    # Keep disabled by default in local development.
    if REQUIRE_API_KEY:
        incoming_api_key = request.headers.get("X-API-Key", "")
        if not API_KEY or not hmac.compare_digest(incoming_api_key, API_KEY):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"}
            )
            response.headers["X-Request-ID"] = request_id
            return response

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response