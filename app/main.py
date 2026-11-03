"""FastAPI entry point for the combined Backend and Agent service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import agent, auth, documents, models, projects, users
from app.core.exceptions import (
    BusinessError,
    handle_business_error,
    handle_http_error,
    handle_unexpected_error,
    handle_validation_error,
)
from app.core.request_logging import RequestLogMiddleware
from app.core.logging_config import timestamp_uvicorn_handlers
from app.db.checkpoint import checkpoint_enabled, open_checkpointer

timestamp_uvicorn_handlers()
logging.getLogger("uvicorn.access").disabled = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.checkpointer = None
    if checkpoint_enabled():
        async with open_checkpointer() as saver:
            app.state.checkpointer = saver
            try:
                yield
            finally:
                app.state.checkpointer = None
    else:
        yield


app = FastAPI(title="Deckwise Python", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)
app.add_exception_handler(BusinessError, handle_business_error)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(StarletteHTTPException, handle_http_error)
app.add_exception_handler(Exception, handle_unexpected_error)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(models.router)
app.include_router(agent.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str) -> dict[str, str]:
    return {"message": f"Hello {name}"}
