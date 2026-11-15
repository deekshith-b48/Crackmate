"""Shared objects, built once. The Groq key stays here on the server and is never sent to the browser."""
from dataclasses import dataclass, replace
import os
from pathlib import Path
import tomllib

from fastapi import Request

from core.config import ROOT, Settings
from core.llm import ModelService
from core.material import Material
from core.storage import Storage
from core.usage import Usage


@dataclass
class Core:
    settings: Settings
    store: Storage
    service: ModelService
    material: Material


def load_settings():
    secrets_file = ROOT / ".streamlit" / "secrets.toml"
    secrets = tomllib.loads(secrets_file.read_text()) if secrets_file.exists() else {}
    settings = Settings.load(secrets)
    if override := os.environ.get("CRACKMATE_DB"):  # lets you try the app on a copy of your data
        settings = replace(settings, database=Path(override))
    return settings


def wire(c):
    """Hooks that need the store: usage logging, and repository facts in project lessons."""
    from api.services import code_context
    if c.service.usage_sink is None:
        c.service.usage_sink = Usage(c.store).add
    if c.material.enrich is None:
        c.material.enrich = lambda record, request: code_context.enrich(c.store, record, request)
    return c


def build_core(settings=None):
    settings = settings or load_settings()
    store = Storage(settings.database)
    service = ModelService(settings)
    return wire(Core(settings, store, service, Material(store, service)))


def core(request: Request) -> Core:
    return request.app.state.core
