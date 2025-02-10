import asyncio

from lnbits.core.models import Payment
from lnbits.core.services import websocket_updater
from lnbits.tasks import register_invoice_listener

from .crud import update_jukebox_payment_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_jukebox")

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "jukebox":
        # not a jukebox invoice
        return

    await update_jukebox_payment_paid(payment.payment_hash)
    await websocket_updater(payment.payment_hash, "paid")
