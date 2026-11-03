"""Validated, process-cached catalog of models this Python backend can call."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CATALOG_PATH = Path(__file__).resolve().parents[1] / "resources" / "model-catalog.json"


class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    providerId: Literal["deepseek", "openrouter"]
    upstreamModelId: str = Field(min_length=1)
    apiFormat: Literal["chat-completions"]
    displayName: str = Field(min_length=1)
    description: str | None = None
    askSupported: bool
    agentSupported: bool
    imageSupported: bool = False
    enabled: bool = True

    @model_validator(mode="after")
    def validate_image_provider(self):
        if self.imageSupported and self.providerId != "openrouter":
            raise ValueError("Only configured OpenRouter models support images")
        return self


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaultModel: str
    models: tuple[ModelDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_model_ids(self):
        ids = [item.id for item in self.models]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate model ID in catalog")
        if self.defaultModel not in {item.id for item in self.models if item.enabled}:
            raise ValueError("Default model must be enabled in catalog")
        return self


@lru_cache(maxsize=1)
def load_catalog() -> ModelCatalog:
    return ModelCatalog.model_validate(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def find_enabled_model(model_id: str) -> ModelDefinition | None:
    return next((item for item in load_catalog().models if item.id == model_id and item.enabled), None)
