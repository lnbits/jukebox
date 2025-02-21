from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from .crud import get_jukebox
from .views_api import api_get_jukebox_device_check

jukebox_generic_router = APIRouter()


def jukebox_renderer():
    return template_renderer(["jukebox/templates"])


@jukebox_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return jukebox_renderer().TemplateResponse(
        "jukebox/index.html", {"request": request, "user": user.json()}
    )


@jukebox_generic_router.get("/{juke_id}", response_class=HTMLResponse)
async def connect_to_jukebox(request: Request, juke_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Jukebox does not exist."
        )
    devices = await api_get_jukebox_device_check(juke_id)
    device_connected = False
    assert jukebox.sp_device
    assert jukebox.sp_playlists
    for device in devices["devices"]:
        if device["id"] == jukebox.sp_device.split("-")[-1]:
            device_connected = True
    if device_connected:
        return jukebox_renderer().TemplateResponse(
            "jukebox/jukebox.html",
            {
                "request": request,
                "playlists": jukebox.sp_playlists.split(","),
                "juke_id": juke_id,
                "price": jukebox.price,
                "inkey": jukebox.inkey,
            },
        )
    else:
        return jukebox_renderer().TemplateResponse(
            "jukebox/error.html",
            {"request": request},
        )
