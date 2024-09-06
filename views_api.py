import base64
import json
from http import HTTPStatus
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from lnbits.core.crud import get_standalone_payment
from lnbits.core.models import WalletTypeInfo
from lnbits.core.services import create_invoice
from lnbits.decorators import require_admin_key
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from .crud import (
    create_jukebox,
    create_jukebox_payment,
    delete_jukebox,
    get_jukebox,
    get_jukebox_payment,
    get_jukeboxs,
    update_jukebox,
    update_jukebox_payment_paid,
)
from .models import CreateJukeboxPayment, CreateJukeLinkData, Jukebox

jukebox_api_router = APIRouter()


@jukebox_api_router.get("/api/v1/jukebox")
async def api_get_jukeboxs(
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    wallet_user = wallet.wallet.user

    try:
        jukeboxs = [jukebox.dict() for jukebox in await get_jukeboxs(wallet_user)]
        return jukeboxs

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.NO_CONTENT, detail="No Jukeboxes"
        ) from exc


##################SPOTIFY AUTH#####################


@jukebox_api_router.get(
    "/api/v1/jukebox/spotify/cb/{juke_id}", response_class=HTMLResponse
)
async def api_check_credentials_callbac(
    juke_id: str,
    code: str = Query(None),
    access_token: str = Query(None),
    refresh_token: str = Query(None),
):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(detail="No Jukebox", status_code=HTTPStatus.FORBIDDEN)
    if code:
        jukebox.sp_access_token = code
        await update_jukebox(jukebox)
    if access_token:
        jukebox.sp_access_token = access_token
        jukebox.sp_refresh_token = refresh_token
        await update_jukebox(jukebox)
    return "<h1>Success!</h1><h2>You can close this window</h2>"


@jukebox_api_router.get(
    "/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)]
)
async def api_check_credentials_check(juke_id: str):
    jukebox = await get_jukebox(juke_id)
    return jukebox


@jukebox_api_router.post(
    "/api/v1/jukebox",
    status_code=HTTPStatus.CREATED,
)
async def api_create_jukebox(
    data: CreateJukeLinkData,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Jukebox:
    return await create_jukebox(key_info.wallet.inkey, data)


@jukebox_api_router.put(
    "/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)]
)
async def api_update_jukebox(data: CreateJukeLinkData, juke_id: str) -> Jukebox:
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="No Jukeboxes")
    for k, v in data.dict().items():
        if v is not None:
            setattr(jukebox, k, v)
    return await update_jukebox(jukebox)


@jukebox_api_router.delete(
    "/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)]
)
async def api_delete_item(juke_id: str):
    await delete_jukebox(juke_id)


################JUKEBOX ENDPOINTS##################


@jukebox_api_router.get("/api/v1/jukebox/jb/playlist/{juke_id}/{sp_playlist}")
async def api_get_jukebox_song(
    juke_id: str,
    sp_playlist: str,
    retry: bool = Query(False),
):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No Jukeboxes")

    tracks = []
    async with httpx.AsyncClient() as client:
        try:
            assert jukebox.sp_access_token
            url: Optional[str] = (
                f"https://api.spotify.com/v1/playlists/{sp_playlist}/tracks"
            )
            while url is not None:
                r = await client.get(
                    url,
                    timeout=40,
                    headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                )
                response = r.json()
                if not response["items"]:
                    if r.status_code == 401:
                        token = await api_get_token(juke_id)
                        if token is False:
                            return False
                        elif retry:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Failed to get auth",
                            )
                        else:
                            return await api_get_jukebox_song(
                                juke_id, sp_playlist, retry=True
                            )
                    return r
                try:
                    for item in response["items"]:
                        if not item["track"] or not item["track"]["id"]:
                            continue
                        tracks.append(
                            {
                                "id": item["track"]["id"],
                                "name": item["track"]["name"],
                                "album": item["track"]["album"]["name"],
                                "artist": item["track"]["artists"][0]["name"],
                                "image": (
                                    item["track"]["album"]["images"][0]["url"]
                                    if item["track"]["album"]["images"]
                                    else None
                                ),
                            }
                        )
                except Exception as e:
                    logger.error(f"Error loop: {e}")
                    pass

                # Check if there are more pages
                url = response.get("next")

        except Exception as e:
            # Handle exceptions appropriately
            logger.error(f"Error: {e}")

    return list(tracks)


######GET ACCESS TOKEN######


async def api_get_token(juke_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No Jukeboxes")

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                "https://accounts.spotify.com/api/token",
                timeout=40,
                params={
                    "grant_type": "refresh_token",
                    "refresh_token": jukebox.sp_refresh_token,
                    "client_id": jukebox.sp_user,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Basic "
                    + base64.b64encode(
                        str(jukebox.sp_user + ":" + jukebox.sp_secret).encode("ascii")
                    ).decode("ascii"),
                },
            )
            if "access_token" not in r.json():
                return False
            else:
                jukebox.sp_access_token = r.json()["access_token"]
                await update_jukebox(jukebox)
        except Exception:
            pass
    return True


######CHECK DEVICE


@jukebox_api_router.get("/api/v1/jukebox/jb/{juke_id}")
async def api_get_jukebox_device_check(juke_id: str, retry: bool = Query(False)):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No Jukeboxes")
    async with httpx.AsyncClient() as client:
        assert jukebox.sp_access_token
        r_device = await client.get(
            "https://api.spotify.com/v1/me/player/devices",
            timeout=40,
            headers={"Authorization": "Bearer " + jukebox.sp_access_token},
        )
        if r_device.status_code in (204, 200):
            return json.loads(r_device.text)
        elif r_device.status_code in (401, 403):
            token = await api_get_token(juke_id)
            if token is False:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, detail="No devices connected"
                )
            elif retry:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, detail="Failed to get auth"
                )
            else:
                return await api_get_jukebox_device_check(juke_id, retry=True)
        else:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="No device connected"
            )


######GET INVOICE STUFF


@jukebox_api_router.get("/api/v1/jukebox/jb/invoice/{juke_id}/{song_id}")
async def api_get_jukebox_invoice(juke_id, song_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No jukebox")
    try:
        assert jukebox.sp_device
        devices = await api_get_jukebox_device_check(juke_id)
        device_connected = False
        for device in devices["devices"]:
            if device["id"] == jukebox.sp_device.split("-")[1]:
                device_connected = True
        if not device_connected:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="No device connected"
            )
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No device connected"
        ) from exc

    invoice = await create_invoice(
        wallet_id=jukebox.wallet,
        amount=jukebox.price,
        memo=jukebox.title,
        extra={"tag": "jukebox"},
    )

    payment_hash = invoice[0]
    data = CreateJukeboxPayment(
        invoice=invoice[1], payment_hash=payment_hash, juke_id=juke_id, song_id=song_id
    )
    jukebox_payment = await create_jukebox_payment(data)
    return jukebox_payment


@jukebox_api_router.get("/api/v1/jukebox/jb/checkinvoice/{pay_hash}/{juke_id}")
async def api_get_jukebox_invoice_check(pay_hash: str, juke_id: str):
    try:
        await get_jukebox(juke_id)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="No jukebox"
        ) from exc
    payment = await get_standalone_payment(pay_hash)
    if not payment:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No payment found")
    status = await payment.check_status()
    if status.paid:
        await update_jukebox_payment_paid(pay_hash)
    return {"paid": status.paid}


@jukebox_api_router.get("/api/v1/jukebox/jb/invoicep/{song_id}/{juke_id}/{pay_hash}")
async def api_get_jukebox_invoice_paid(
    song_id: str,
    juke_id: str,
    pay_hash: str,
    retry: bool = Query(False),
):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No jukebox")
    await api_get_jukebox_invoice_check(pay_hash, juke_id)
    jukebox_payment = await get_jukebox_payment(pay_hash)
    if jukebox_payment and jukebox_payment.paid:
        async with httpx.AsyncClient() as client:
            assert jukebox.sp_access_token
            r = await client.get(
                "https://api.spotify.com/v1/me/player/currently-playing?market=ES",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            r_device = await client.get(
                "https://api.spotify.com/v1/me/player",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            is_playing = False
            if r_device.status_code == 200:
                is_playing = r_device.json()["is_playing"]

            if r.status_code == 204 or is_playing is False:
                async with httpx.AsyncClient() as client:
                    uri = ["spotify:track:" + song_id]
                    assert jukebox.sp_device
                    r = await client.put(
                        "https://api.spotify.com/v1/me/player/play?device_id="
                        + jukebox.sp_device.split("-")[1],
                        json={"uris": uri},
                        timeout=40,
                        headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                    )
                    if r.status_code == 204:
                        return jukebox_payment
                    elif r.status_code in (401, 403):
                        token = await api_get_token(juke_id)
                        if token is False:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Invoice not paid",
                            )
                        elif retry:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Failed to get auth",
                            )
                        else:
                            return api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash, retry=True
                            )
                    else:
                        raise HTTPException(
                            status_code=HTTPStatus.FORBIDDEN, detail="Invoice not paid"
                        )
            elif r.status_code == 200:
                async with httpx.AsyncClient() as client:
                    assert jukebox.sp_access_token
                    assert jukebox.sp_device
                    r = await client.post(
                        "https://api.spotify.com/v1/me/player/queue?uri=spotify%3Atrack%3A"
                        + song_id
                        + "&device_id="
                        + jukebox.sp_device.split("-")[1],
                        timeout=40,
                        headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                    )
                    if r.status_code == 204:
                        return jukebox_payment

                    elif r.status_code in (401, 403):
                        token = await api_get_token(juke_id)
                        if token is False:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Invoice not paid",
                            )
                        elif retry:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Failed to get auth",
                            )
                        else:
                            return await api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash
                            )
                    else:
                        raise HTTPException(
                            status_code=HTTPStatus.OK, detail="Invoice not paid"
                        )
            elif r.status_code in (401, 403):
                token = await api_get_token(juke_id)
                if token is False:
                    raise HTTPException(
                        status_code=HTTPStatus.OK, detail="Invoice not paid"
                    )
                elif retry:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN, detail="Failed to get auth"
                    )
                else:
                    return await api_get_jukebox_invoice_paid(
                        song_id, juke_id, pay_hash
                    )
    raise HTTPException(status_code=HTTPStatus.OK, detail="Invoice not paid")


############################GET QUEUE


@jukebox_api_router.get("/api/v1/jukebox/jb/queue/{juke_id}")
async def api_get_jukebox_queue(
    juke_id: str,
):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No jukebox")
    async with httpx.AsyncClient() as client:
        try:
            assert jukebox.sp_access_token
            r = await client.get(
                "https://api.spotify.com/v1/me/player/queue",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            if r.status_code == 204:
                raise HTTPException(status_code=HTTPStatus.OK, detail="Nothing")
            elif r.status_code == 200:
                try:
                    response = r.json()
                    track = None
                    if response["currently_playing"] not in (None, ""):
                        item = response["currently_playing"]
                        track = {
                            "id": item["id"],
                            "name": item["name"],
                            "album": item["album"]["name"],
                            "artist": item["artists"][0]["name"],
                            "image": item["album"]["images"][0]["url"],
                        }
                    tracks = []
                    for _item in response["queue"]:
                        tracks.append(
                            {
                                "id": _item["id"],
                                "name": _item["name"],
                                "album": _item["album"]["name"],
                                "artist": _item["artists"][0]["name"],
                                "image": _item["album"]["images"][0]["url"],
                            }
                        )
                    return {"playing": track, "queue": tracks}
                except Exception as exc:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND, detail="Something went wrong"
                    ) from exc

            elif r.status_code == 401:
                token = await api_get_token(juke_id)
                if token is False:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN, detail="Invoice not paid"
                    )
            else:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, detail="Something went wrong"
                )
        except Exception as exc:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Something went wrong, or no song is playing yet",
            ) from exc
