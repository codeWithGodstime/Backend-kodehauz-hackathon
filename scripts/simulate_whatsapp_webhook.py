"""Post a mix of enquiry and order messages to the local WhatsApp webhook.

Each request is a WhatsApp Cloud API inbound webhook (entry/changes/value).
The business number in ``metadata.display_phone_number`` is the seeded
connected line (``app.seed.demo.BUSINESS_DISPLAY_PHONE_NUMBER``). The backend
resolves the workspace from that number.

Message ids are fixed (``wamid.sim.*``). Running this again is safe: the
worker keeps the first row for each id and does not insert a duplicate.

The HTTP body from this app is ``{"status": "accepted"}``. That is the
webhook acknowledgement. This service does not call the Graph send-message
API, so there is no ``messages[0].id`` send response to mimic. The inbound
payload itself includes ``messaging_product``, ``contacts``, and ``messages``.

Usage (from the backend repo root, with META_APP_SECRET matching the API):

    python scripts/simulate_whatsapp_webhook.py
    python scripts/simulate_whatsapp_webhook.py --base-url http://localhost:8000/api/v1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ingestion.signature import meta_body_signature
from app.seed.demo import (
    BUSINESS_DISPLAY_PHONE_NUMBER,
    BUSINESS_PHONE_NUMBER_ID,
)

MESSAGES: tuple[dict[str, str], ...] = (
    {
        "provider_message_id": "wamid.sim.enquiry.1",
        "sender": "2348091001001",
        "sender_name": "Chioma",
        "body": "What time do you close today?",
    },
    {
        "provider_message_id": "wamid.sim.order.1",
        "sender": "2348091001002",
        "sender_name": "Emeka",
        "body": "I want 2 plates of jollof rice. Deliver to Lekki phase 1",
    },
    {
        "provider_message_id": "wamid.sim.enquiry.2",
        "sender": "2348091001003",
        "sender_name": "Ngozi",
        "body": "How much is a plate of fried rice?",
    },
    {
        "provider_message_id": "wamid.sim.order.2",
        "sender": "2348091001001",
        "sender_name": "Chioma",
        "body": "Please send me 1 pack of moi moi and 3 meat pies",
    },
    {
        "provider_message_id": "wamid.sim.enquiry.3",
        "sender": "2348091001002",
        "sender_name": "Emeka",
        "body": "Do you deliver to Ikeja?",
    },
    {
        "provider_message_id": "wamid.sim.order.3",
        "sender": "2348091001003",
        "sender_name": "Ngozi",
        "body": "I'd like 4 portions of pounded yam. Address: 12 Allen Avenue",
    },
)


def webhook_payload(message: dict[str, str], *, index: int) -> dict:
    """One Cloud API ``messages`` notification sent to the seeded business line."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_SIM",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": BUSINESS_DISPLAY_PHONE_NUMBER,
                                "phone_number_id": BUSINESS_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": message["sender_name"]},
                                    "wa_id": message["sender"],
                                }
                            ],
                            "messages": [
                                {
                                    "from": message["sender"],
                                    "id": message["provider_message_id"],
                                    "timestamp": str(1710000000 + index),
                                    "type": "text",
                                    "text": {"body": message["body"]},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def post_message(url: str, secret: str, message: dict[str, str], *, index: int) -> int:
    payload = webhook_payload(message, index=index)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": meta_body_signature(body, secret),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    print(
        f"POST {url} to={BUSINESS_DISPLAY_PHONE_NUMBER} "
        f"id={message['provider_message_id']} HTTP {status} {raw}"
    )
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SOCIALCHEF_API_URL", "http://localhost:8000/api/v1"),
        help="API prefix, default http://localhost:8000/api/v1",
    )
    args = parser.parse_args(argv)
    secret = os.environ.get("META_APP_SECRET", "").strip()
    if not secret:
        print("Set META_APP_SECRET to the same value the API uses.", file=sys.stderr)
        return 1
    url = args.base_url.rstrip("/") + "/webhooks/whatsapp/inbound"
    print(f"Sending {len(MESSAGES)} messages to {BUSINESS_DISPLAY_PHONE_NUMBER}")
    failures = 0
    for index, message in enumerate(MESSAGES):
        status = post_message(url, secret, message, index=index)
        if status != 200:
            failures += 1
    if failures:
        print(f"{failures} request(s) were not accepted.")
        return 1
    print("All requests accepted. Re-running uses the same message ids and does not duplicate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
