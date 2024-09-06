from typing import Optional

from lnbits.db import Database
from lnbits.helpers import insert_query, update_query, urlsafe_short_hash

from .models import CreateJukeboxPayment, CreateJukeLinkData, Jukebox, JukeboxPayment

db = Database("ext_jukebox")


async def create_jukebox(inkey: str, data: CreateJukeLinkData) -> Jukebox:
    juke_id = urlsafe_short_hash()
    jukebox = Jukebox(
        id=juke_id,
        inkey=inkey,
        user=data.user,
        title=data.title,
        wallet=data.wallet,
        sp_user=data.sp_user,
        sp_secret=data.sp_secret,
        sp_access_token=data.sp_access_token,
        sp_refresh_token=data.sp_refresh_token,
        sp_device=data.sp_device,
        sp_playlists=data.sp_playlists,
        price=int(data.price),
        profit=0,
    )
    await db.execute(
        insert_query("jukebox.jukebox", jukebox),
        jukebox.dict(),
    )
    return jukebox


async def update_jukebox(data: Jukebox) -> Jukebox:
    jukebox = await db.execute(
        update_query("jukebox.jukebox", data),
        data.dict(),
    )
    return jukebox


async def get_jukebox(juke_id: str) -> Optional[Jukebox]:
    row = await db.fetchone(
        "SELECT * FROM jukebox.jukebox WHERE id = :id", {"id": juke_id}
    )
    return Jukebox(**row) if row else None


async def get_jukebox_by_user(user: str) -> Optional[Jukebox]:
    row = await db.fetchone(
        "SELECT * FROM jukebox.jukebox WHERE sp_user = :user", {"user": user}
    )
    return Jukebox(**row) if row else None


async def get_jukeboxs(user: str) -> list[Jukebox]:
    rows = await db.fetchall(
        'SELECT * FROM jukebox.jukebox WHERE "user" = :user', {"user": user}
    )
    for row in rows:
        if row["sp_playlists"] is None:
            await delete_jukebox(row["id"])
    rows = await db.fetchall(
        'SELECT * FROM jukebox.jukebox WHERE "user" = :user', {"user": user}
    )

    return [Jukebox(**row) for row in rows]


async def delete_jukebox(juke_id: str):
    await db.execute(
        "DELETE FROM jukebox.jukebox WHERE id = :id",
        {"id": juke_id},
    )


async def create_jukebox_payment(data: CreateJukeboxPayment) -> JukeboxPayment:
    jukebox_payment = JukeboxPayment(
        payment_hash=data.payment_hash,
        juke_id=data.juke_id,
        song_id=data.song_id,
        paid=False,
    )
    await db.execute(
        insert_query("jukebox.jukebox_payment", jukebox_payment),
        jukebox_payment.dict(),
    )
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
    row = await db.fetchone(
        "SELECT * FROM jukebox.jukebox_payment WHERE payment_hash = :payment_hash",
        {"payment_hash": payment_hash},
    )
    return JukeboxPayment(**row) if row else None
