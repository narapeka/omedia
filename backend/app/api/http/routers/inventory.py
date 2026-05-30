from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from app.api.http.deps import Inventory
from app.api.http.present.inventory import present_directory_listing
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.inventory import DirectoryListing

router = APIRouter(prefix="/inventory", tags=["inventory"], responses=DEFAULT_API_RESPONSES)


@router.get("/directories", response_model=DirectoryListing)
def list_inventory_directories(
    inventory: Inventory,
    path: Path | None = Query(default=None),
) -> DirectoryListing:
    return present_directory_listing(inventory.browse_directories(path))
