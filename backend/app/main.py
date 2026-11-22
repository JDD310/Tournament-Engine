from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db import Base, engine
from app.routers import tournaments

FIELD_LABELS = {"name": "Tournament name", "game": "Game", "format": "Format"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # No migrations yet; create tables on startup. Replace with Alembic once
    # the schema starts changing (see PR follow-ups).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Tournament Engine", lifespan=lifespan)
app.include_router(tournaments.router)


def _friendly_message(error: dict) -> str:
    field = error["loc"][-1] if error["loc"] else ""
    label = FIELD_LABELS.get(str(field), str(field).capitalize())
    if error["type"] == "missing":
        return f"{label} is required."
    if error["type"] == "enum" and field == "format":
        return "Format must be single_elimination."
    message = error["msg"]
    # Messages raised by our own validators come through as "Value error, ...".
    return message.removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part != "body"),
            "message": _friendly_message(err),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Please fix the highlighted fields.", "errors": errors},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
