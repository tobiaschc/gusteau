from __future__ import annotations

from fastapi import APIRouter

from .deps import StoreDep
from .schemas import Health, Settings, SettingsIn

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=Settings)
def get_settings(store: StoreDep):
    return store.settings()


@router.put("/settings", response_model=Settings)
def put_settings(body: SettingsIn, store: StoreDep):
    return store.save_settings(body.model_dump(exclude_none=True))


@router.get("/health", response_model=Health)
def health():
    return Health(ok=True)
