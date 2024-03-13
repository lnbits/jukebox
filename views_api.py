import base64
import json
from http import HTTPStatus
from typing import Optional
from urllib import response

import httpx
from fastapi import Depends, Query
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from loguru import logger

from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, require_admin_key

from . import jukebox_ext
from .crud import (
    create_jukebox,
    create_jukebox_payment,
    delete_jukebox,
    get_jukebox,
    get_jukebox_payment,
    get_jukeboxs,
    update_jukebox,
    update_jukebox_payment,
)
from .models import CreateJukeboxPayment, CreateJukeLinkData, Jukebox


@jukebox_ext.get("/api/v1/jukebox")
async def api_get_jukeboxs(
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    wallet_user = wallet.wallet.user

    try:
        jukeboxs = [jukebox.dict() for jukebox in await get_jukeboxs(wallet_user)]
        return jukeboxs

    except:
        raise HTTPException(status_code=HTTPStatus.NO_CONTENT, detail="No Jukeboxes")


##################SPOTIFY AUTH#####################


@jukebox_ext.get("/api/v1/jukebox/spotify/cb/{juke_id}", response_class=HTMLResponse)
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
        await update_jukebox(jukebox, juke_id=juke_id)
    if access_token:
        jukebox.sp_access_token = access_token
        jukebox.sp_refresh_token = refresh_token
        await update_jukebox(jukebox, juke_id=juke_id)
    return "<h1>Success!</h1><h2>You can close this window</h2>"


@jukebox_ext.get("/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)])
async def api_check_credentials_check(juke_id: str):
    jukebox = await get_jukebox(juke_id)
    return jukebox


@jukebox_ext.post(
    "/api/v1/jukebox",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(require_admin_key)],
)
async def api_create_jukebox(data: CreateJukeLinkData) -> Jukebox:
    return await create_jukebox(data)


@jukebox_ext.put("/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)])
async def api_update_jukebox(data: CreateJukeLinkData, juke_id: str) -> Jukebox:
    return await update_jukebox(data, juke_id=juke_id)


@jukebox_ext.delete(
    "/api/v1/jukebox/{juke_id}", dependencies=[Depends(require_admin_key)]
)
async def api_delete_item(juke_id: str):
    await delete_jukebox(juke_id)
    # try:
    #     return [{**jukebox} for jukebox in await get_jukeboxs(wallet.wallet.user)]
    # except:
    #     raise HTTPException(status_code=HTTPStatus.NO_CONTENT, detail="No Jukebox")


################JUKEBOX ENDPOINTS##################


@jukebox_ext.get("/api/v1/jukebox/jb/playlist/{juke_id}/{sp_playlist}")
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
            url = f"https://api.spotify.com/v1/playlists/{sp_playlist}/tracks"
            while url is not None:
                r = await client.get(
                    url,
                    timeout=40,
                    headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                )
                response = r.json()
                logger.debug(f"#####URL: {url}")
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
                        if not item["track"]:
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
                url = response["next"] or None
                logger.debug(f"#####NEXT: {url}")

        except Exception as e:
            # Handle exceptions appropriately
            logger.error(f"Error: {e}")

    return [track for track in tracks]


# @jukebox_ext.get("/api/v1/jukebox/jb/playlist/{juke_id}/{sp_playlist}")
# async def api_get_jukebox_song(
#     juke_id: str,
#     sp_playlist: str,
#     retry: bool = Query(False),
# ):
#     jukebox = await get_jukebox(juke_id)
#     if not jukebox:
#         raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No Jukeboxes")
#     tracks = []
#     async with httpx.AsyncClient() as client:
#         try:
#             assert jukebox.sp_access_token
#             r = await client.get(
#                 "https://api.spotify.com/v1/playlists/" + sp_playlist + "/tracks",
#                 timeout=40,
#                 headers={"Authorization": "Bearer " + jukebox.sp_access_token},
#             )
#             if "items" not in r.json():
#                 if r.status_code == 401:
#                     token = await api_get_token(juke_id)
#                     if token is False:
#                         return False
#                     elif retry:
#                         raise HTTPException(
#                             status_code=HTTPStatus.FORBIDDEN,
#                             detail="Failed to get auth",
#                         )
#                     else:
#                         return await api_get_jukebox_song(
#                             juke_id, sp_playlist, retry=True
#                         )
#                 return r
#             for item in r.json()["items"]:
#                 tracks.append(
#                     {
#                         "id": item["track"]["id"],
#                         "name": item["track"]["name"],
#                         "album": item["track"]["album"]["name"],
#                         "artist": item["track"]["artists"][0]["name"],
#                         "image": item["track"]["album"]["images"][0]["url"],
#                     }
#                 )
#         except:
#             pass
#     return [track for track in tracks]

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
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if "access_token" not in r.json():
                return False
            else:
                jukebox.sp_access_token = r.json()["access_token"]
                await update_jukebox(jukebox, juke_id=juke_id)
        except:
            pass
    return True


######CHECK DEVICE


@jukebox_ext.get("/api/v1/jukebox/jb/{juke_id}")
async def api_get_jukebox_device_check(juke_id: str, retry: bool = Query(False)):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No Jukeboxes")
    async with httpx.AsyncClient() as client:
        assert jukebox.sp_access_token
        rDevice = await client.get(
            "https://api.spotify.com/v1/me/player/devices",
            timeout=40,
            headers={"Authorization": "Bearer " + jukebox.sp_access_token},
        )
        if rDevice.status_code in (204, 200):
            return json.loads(rDevice.text)
        elif rDevice.status_code in (401, 403):
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


@jukebox_ext.get("/api/v1/jukebox/jb/invoice/{juke_id}/{song_id}")
async def api_get_jukebox_invoice(juke_id, song_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No jukebox")
    try:

        assert jukebox.sp_device
        devices = await api_get_jukebox_device_check(juke_id)
        deviceConnected = False
        for device in devices["devices"]:
            if device["id"] == jukebox.sp_device.split("-")[1]:
                deviceConnected = True
        if not deviceConnected:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="No device connected"
            )
    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No device connected"
        )

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


@jukebox_ext.get("/api/v1/jukebox/jb/checkinvoice/{pay_hash}/{juke_id}")
async def api_get_jukebox_invoice_check(pay_hash: str, juke_id: str):
    try:
        await get_jukebox(juke_id)
    except:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No jukebox")
    try:
        status = await api_payment(pay_hash)
        if status["paid"]:
            await update_jukebox_payment(pay_hash, paid=True)
            return {"paid": True}
    except:
        return {"paid": False}

    return {"paid": False}


@jukebox_ext.get("/api/v1/jukebox/jb/invoicep/{song_id}/{juke_id}/{pay_hash}")
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
            rDevice = await client.get(
                "https://api.spotify.com/v1/me/player",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            isPlaying = False
            if rDevice.status_code == 200:
                isPlaying = rDevice.json()["is_playing"]

            if r.status_code == 204 or isPlaying is False:
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


@jukebox_ext.get("/api/v1/jukebox/jb/queue/{juke_id}")
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
                except:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND, detail="Something went wrong"
                    )

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
        except:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Something went wrong, or no song is playing yet",
            )
