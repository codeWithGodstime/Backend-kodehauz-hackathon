"""Fulfilment listener for msflib payment verification."""

from msflib.eventbus import AppEmitter

from app.billing.gateway import install_plan_gateway
from app.billing.subscriptions import QUEUE_EVENT_KEY, fulfil_paid_subscription

SUBSCRIPTION_EVENT = f"payment-queue-execute-{QUEUE_EVENT_KEY}"


def register_subscription_fulfilment(app_emitter: AppEmitter) -> None:
    install_plan_gateway()

    @app_emitter.on(SUBSCRIPTION_EVENT)
    async def activate_paid_subscription(queue, options):
        await fulfil_paid_subscription(queue, options["session"])
