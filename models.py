from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateJukeLinkData(BaseModel):
    user: str | None = Query(None)
    title: str | None = Query(None)
    wallet: str | None = Query(None)
    sp_user: str | None = Query(None)
    sp_secret: str | None = Query(None)
    sp_access_token: str | None = Query(None)
    sp_refresh_token: str | None = Query(None)
    sp_device: str | None = Query(None)
    sp_playlists: str | None = Query(None)
    price: int | None = Query(None)


class Jukebox(BaseModel):
    id: str
    user: str
    title: str
    wallet: str
    inkey: Optional[str] = None
    sp_user: str
    sp_secret: str
    sp_access_token: Optional[str] = None
    sp_refresh_token: Optional[str] = None
    sp_device: Optional[str] = None
    sp_playlists: Optional[str] = None
    price: int
    profit: int


class JukeboxPayment(BaseModel):
    payment_hash: str
    juke_id: str
    song_id: str
    paid: bool


class CreateJukeboxPayment(BaseModel):
    invoice: str | None = Query(None)
    payment_hash: str | None = Query(None)
    juke_id: str | None = Query(None)
    song_id: str | None = Query(None)
    paid: bool = Query(False)
