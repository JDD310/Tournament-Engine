from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import teams, tournaments

FIELD_LABELS = {
    "name": "Tournament name",
    "game": "Game",
    "format": "Format",
    "team_ids": "Team order",
}


# The schema is managed by Alembic. Run `python -m app.migrate` (or
# `alembic upgrade head`) before starting the app; it does not create tables.
app = FastAPI(title="Tournament Engine")
app.include_router(tournaments.router)
app.include_router(teams.router)


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
