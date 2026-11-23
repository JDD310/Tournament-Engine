from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.routers import bracket, matches, public, teams, tournaments
from app.spa import install_spa

FIELD_LABELS = {
    "name": "Tournament name",
    "game": "Game",
    "format": "Format",
    "team_ids": "Team order",
    "team1_score": "Team 1 score",
    "team2_score": "Team 2 score",
}


# The schema is managed by Alembic. Run `python -m app.migrate` (or
# `alembic upgrade head`) before starting the app; it does not create tables.
app = FastAPI(title="Tournament Engine")


class ReferrerPolicyMiddleware:
    """Send ``Referrer-Policy: same-origin`` on every response.

    index.html already has the matching <meta> tag; the header also covers
    API responses and anything else the browser loads from this origin.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"referrer-policy"
                ]
                headers.append((b"referrer-policy", b"same-origin"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


app.add_middleware(ReferrerPolicyMiddleware)
app.include_router(tournaments.router)
app.include_router(teams.router)
app.include_router(bracket.router)
app.include_router(matches.router)
app.include_router(public.router)


def _field_name(error: dict) -> str:
    # loc starts with where the value came from ("body", "path", ...). The rest
    # names the field; integers there are character offsets or list indexes.
    return ".".join(part for part in error["loc"][1:] if isinstance(part, str))


def _body_message(error: dict) -> str:
    """Message for an error about the request body as a whole."""
    if error["type"] == "json_invalid":
        return "Request body must be valid JSON."
    if error["type"] == "missing":
        return "Request body is required."
    return "Request body must be a JSON object."


def _friendly_message(error: dict, field: str) -> str:
    label = FIELD_LABELS.get(field, field.capitalize())
    if error["type"] == "missing":
        return f"{label} is required."
    if error["type"] == "enum" and field == "format":
        return "Format must be single_elimination."
    message = error["msg"]
    # Messages raised by our own validators come through as "Value error, ...".
    return message.removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = _field_name(err)
        message = _friendly_message(err, field) if field else _body_message(err)
        errors.append({"field": field, "message": message})
    body_errors = [e["message"] for e in errors if not e["field"]]
    detail = body_errors[0] if body_errors else "Please fix the highlighted fields."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail, "errors": errors},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Registered last so the API routes above always take precedence.
if get_settings().frontend_dist:
    install_spa(app, Path(get_settings().frontend_dist))
