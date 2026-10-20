from typing import Optional

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import CreateJukeboxPayment, CreateJukeLinkData, Jukebox, JukeboxPayment

db = Database("ext_jukebox")


async def create_jukebox(inkey: str, data: CreateJukeLinkData) -> Jukebox:
    juke_id = urlsafe_short_hash()
    jukebox = Jukebox.model_validate(
        {**data.model_dump(), "id": juke_id, "inkey": inkey, "profit": 0}
    )
    await db.insert("jukebox.jukebox", jukebox)
    return jukebox


async def update_jukebox(jukebox: Jukebox) -> Jukebox:
    await db.update("jukebox.jukebox", jukebox)
    return jukebox


async def get_jukebox(juke_id: str) -> Optional[Jukebox]:
    return await db.fetchone(
        "SELECT * FROM jukebox.jukebox WHERE id = :id", {"id": juke_id}, Jukebox
    )


async def get_jukebox_by_user(user: str) -> Optional[Jukebox]:
    return await db.fetchone(
        "SELECT * FROM jukebox.jukebox WHERE sp_user = :user",
        {"user": user},
        Jukebox,
    )


async def get_jukeboxs(user: str) -> list[Jukebox]:
    jukeboxes = await db.fetchall(
        'SELECT * FROM jukebox.jukebox WHERE "user" = :user',
        {"user": user},
        Jukebox,
    )
    _jukeboxes = []
    for jukebox in jukeboxes:
        if jukebox.sp_playlists is None:
            await delete_jukebox(jukebox.id)
        else:
            _jukeboxes.append(jukebox)
    return _jukeboxes


async def delete_jukebox(juke_id: str):
    await db.execute(
        "DELETE FROM jukebox.jukebox WHERE id = :id",
        {"id": juke_id},
    )


async def create_jukebox_payment(data: CreateJukeboxPayment) -> JukeboxPayment:
    jukebox_payment = JukeboxPayment.model_validate(
        {**data.model_dump(), "paid": False}
    )
    await db.insert("jukebox.jukebox_payment", jukebox_payment)
    return jukebox_payment


async def update_jukebox_payment_paid(payment_hash: str) -> None:
    await db.execute(
        """
        UPDATE jukebox.jukebox_payment
        SET paid = True WHERE payment_hash = :payment_hash
        """,
        {"payment_hash": payment_hash},
    )


async def get_jukebox_payment(payment_hash: str) -> Optional[JukeboxPayment]:
    return await db.fetchone(
        "SELECT * FROM jukebox.jukebox_payment WHERE payment_hash = :payment_hash",
        {"payment_hash": payment_hash},
        JukeboxPayment,
    )
