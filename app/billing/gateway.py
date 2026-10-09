"""Paystack gateway that can attach a subscription plan on initialize."""

import httpx
from msflib.models import AccountStub
from msflib.payments.models import PaymentData, PaymentInfo, PaymentStatus
from msflib.payments.service.error import PaymentConnectionError, PaymentResponseError
from msflib.payments.service.paystack_gateway import PaystackGateway

from app.billing.plan_context import paystack_plan_code


class PlanPaystackGateway(PaystackGateway):
    """Same initiate request as msflib, plus Paystack's ``plan`` field when set."""

    async def initiate(self, account: AccountStub, data: PaymentData) -> PaymentInfo:
        payload = {
            "email": data.email,
            "amount": self.convert_amount(amount=data.amount),
            "callback_url": data.callback_url or self.settings.PAYMENT_CALLBACK_URL,
            "metadata": {"cancel_action": data.cancel_url or self.settings.PAYMENT_CANCEL_URL},
        }
        plan_code = paystack_plan_code.get()
        if plan_code:
            payload["plan"] = plan_code

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=10.0)) as client:
                response = await client.post(
                    f"{self.settings.PAYSTACK_BASE_URL}/transaction/initialize",
                    headers={"Authorization": f"Bearer {self.settings.PAYSTACK_SECRET_KEY}"},
                    json=payload,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.logger.error("HTTPException occurred, detail:%s", exc)
            raise PaymentResponseError(
                "Paystack service returned an error", cause=str(exc)
            ) from exc
        except httpx.RequestError as exc:
            self.logger.error("HTTPException occurred, detail:%s", exc)
            raise PaymentConnectionError("Could not connect to Paystack", cause=str(exc)) from exc

        trx_json = response.json()
        if not trx_json.get("status") or not isinstance(trx_json.get("data"), dict):
            self.logger.error("Paystack returned malformed response")
            raise PaymentResponseError(
                "Malformed or unsuccessful Paystack response", cause="Invalid response json"
            )
        transaction_data = trx_json["data"]
        return PaymentInfo(
            **data.model_dump(),
            account_id=account.id,
            authorization_url=transaction_data["authorization_url"],
            access_code=transaction_data["access_code"],
            reference=transaction_data["reference"],
            status=PaymentStatus.unverified,
            data={"cancel_action": data.cancel_url or self.settings.PAYMENT_CANCEL_URL},
        )


def install_plan_gateway() -> None:
    """Point ``process_payment`` at ``PlanPaystackGateway``."""
    from msflib.payments.service import processor

    if processor.PaystackGateway is not PlanPaystackGateway:
        processor.PaystackGateway = PlanPaystackGateway
