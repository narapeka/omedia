from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.services.activity.query import ActivityQueryService
from app.services.admin.service import AdminService
from app.services.config.service import ConfigurationService
from app.services.depot.service import DepotService
from app.services.inventory.service import InventoryService
from app.services.organize.service import OrganizeService
from app.services.transfer.schedule import TransferService
from app.services.watch.service import WatchService


def _services(request: Request):
    return request.app.state.runtime_manager.get()


def get_activity_service(request: Request) -> ActivityQueryService:
    return _services(request).activity


def get_admin_service(request: Request) -> AdminService:
    return _services(request).admin_service


def get_config_service(request: Request) -> ConfigurationService:
    return _services(request).configuration


def get_depot_service(request: Request) -> DepotService:
    return _services(request).depot_service


def get_inventory_service(request: Request) -> InventoryService:
    return _services(request).inventory


def get_organize_service(request: Request) -> OrganizeService:
    return _services(request).organize_pipeline


def get_transfer_service(request: Request) -> TransferService:
    return _services(request).transfer_service


def get_watch_service(request: Request) -> WatchService:
    return _services(request).watch_automation


Activity = Annotated[ActivityQueryService, Depends(get_activity_service)]
Admin = Annotated[AdminService, Depends(get_admin_service)]
Config = Annotated[ConfigurationService, Depends(get_config_service)]
Depot = Annotated[DepotService, Depends(get_depot_service)]
Inventory = Annotated[InventoryService, Depends(get_inventory_service)]
Organize = Annotated[OrganizeService, Depends(get_organize_service)]
Transfer = Annotated[TransferService, Depends(get_transfer_service)]
Watch = Annotated[WatchService, Depends(get_watch_service)]
