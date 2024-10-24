import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import jukebox_generic_router
from .views_api import jukebox_api_router

jukebox_static_files = [
    {
        "path": "/jukebox/static",
        "name": "jukebox_static",
    }
]

jukebox_ext: APIRouter = APIRouter(prefix="/jukebox", tags=["jukebox"])
jukebox_ext.include_router(jukebox_generic_router)
jukebox_ext.include_router(jukebox_api_router)

scheduled_tasks: list[asyncio.Task] = []


def jukebox_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def jukebox_start():
    from lnbits.tasks import create_permanent_unique_task

    task = create_permanent_unique_task("ext_jukebox", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = ["jukebox_ext", "jukebox_static_files", "jukebox_start", "jukebox_stop", "db"]
