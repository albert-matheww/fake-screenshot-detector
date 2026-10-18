"""Shared constants and small helpers."""
from __future__ import annotations

import math
from typing import Tuple

TYPES = ["payment_receipt", "bank_statement", "order_invoice", "chat", "social_post", "message_alert", "web_page"]
TYPE_LABELS = {
    "payment_receipt": "Payment receipt or transfer",
    "bank_statement": "Bank statement or balance",
    "order_invoice": "Order, invoice or refund",
    "chat": "Chat conversation",
    "social_post": "Social media post",
    "message_alert": "SMS, e-mail or notification",
    "web_page": "Web page or dashboard",
    "unknown": "Unknown type",
}

# Chrome-generator families (data/chrome manifest) -> coarse types, used for training and testing the router
FAMILY_TO_TYPE = {
    "chat": "chat", "group_chat": "chat",
    "upi_receipt": "payment_receipt", "ride_receipt": "payment_receipt",
    "bank_balance": "bank_statement", "bank_statement": "bank_statement",
    "ecom_order": "order_invoice", "desktop_invoice": "order_invoice",
    "social_post": "social_post",
    "email_inbox": "message_alert", "email_view": "message_alert", "notifications": "message_alert", "sms_otp": "message_alert",
    "crypto_wallet": "web_page", "stock_portfolio": "web_page", "desktop_dashboard": "web_page",
}


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
