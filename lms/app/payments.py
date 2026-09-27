"""Razorpay integration.

Live mode: needs RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET env vars.
Stub mode (no keys): orders are fake and payments complete instantly —
the full enrollment flow works end-to-end without real money.
"""
import hashlib
import hmac
import uuid

import requests
from flask import current_app

RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


def is_live():
    return bool(current_app.config.get("PAYMENTS_LIVE"))


def create_order(amount_inr, receipt, notes=None):
    """Create a Razorpay order. Returns dict with at least id/amount/currency/stub."""
    amount_paise = int(amount_inr * 100)
    if not is_live():
        return {
            "stub": True,
            "id": "order_stub_" + uuid.uuid4().hex[:14],
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
        }
    key_id = current_app.config["RAZORPAY_KEY_ID"]
    key_secret = current_app.config["RAZORPAY_KEY_SECRET"]
    resp = requests.post(
        RAZORPAY_ORDERS_URL,
        auth=(key_id, key_secret),
        json={"amount": amount_paise, "currency": "INR", "receipt": receipt,
              "notes": notes or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    data["stub"] = False
    return data


def verify_payment_signature(order_id, payment_id, signature):
    """Verify Razorpay checkout signature (live mode only)."""
    secret = current_app.config["RAZORPAY_KEY_SECRET"]
    body = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
