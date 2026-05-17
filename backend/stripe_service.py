"""Stripe サブスクリプション管理"""
import os
import time
import sqlite3
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY    = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_ID      = os.environ.get('STRIPE_PRICE_ID', '')
SUBSCRIPTION_DB      = Path(os.environ.get('SUBSCRIPTION_DB', './subscription.db'))

# Premium platforms (free = uword only)
PREMIUM_PLATFORMS = {"instagram", "facebook", "threads", "note", "x_twitter", "linkedin", "umatching"}


def _get_stripe():
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def init_db():
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                email                  TEXT PRIMARY KEY,
                stripe_customer_id     TEXT,
                stripe_subscription_id TEXT,
                status                 TEXT DEFAULT 'inactive',
                current_period_end     INTEGER,
                created_at             TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at             TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    logger.info("[stripe] subscription DB initialized: %s", SUBSCRIPTION_DB)


def get_status(email: str) -> dict:
    """メールアドレスでサブスク状態を返す"""
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        row = conn.execute(
            'SELECT status, current_period_end FROM subscriptions WHERE email=?',
            (email,)
        ).fetchone()
    if not row:
        return {'status': 'inactive', 'is_premium': False}
    is_active = row[0] == 'active' and (row[1] is None or row[1] > int(time.time()))
    return {'status': row[0], 'is_premium': is_active}


def create_checkout_session(email: str, success_url: str, cancel_url: str) -> str:
    stripe = _get_stripe()
    session = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=['card'],
        line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
        mode='subscription',
        success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=cancel_url,
    )
    return session.url


def create_portal_session(email: str, return_url: str) -> str:
    """顧客がサブスクを管理できるStripeポータルURL"""
    stripe = _get_stripe()
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        row = conn.execute(
            'SELECT stripe_customer_id FROM subscriptions WHERE email=?',
            (email,)
        ).fetchone()
    if not row or not row[0]:
        raise ValueError("customer not found")
    session = stripe.billing_portal.Session.create(
        customer=row[0],
        return_url=return_url,
    )
    return session.url


def handle_webhook(payload: bytes, sig_header: str) -> str:
    stripe = _get_stripe()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")

    etype = event['type']
    logger.info("[stripe] webhook: %s", etype)

    if etype == 'checkout.session.completed':
        s = event['data']['object']
        _upsert(s.get('customer_email'), s.get('customer'), s.get('subscription'), 'active', None)

    elif etype in ('customer.subscription.updated', 'customer.subscription.deleted'):
        sub = event['data']['object']
        _update_by_customer(sub['customer'], sub['status'], sub.get('current_period_end'))

    elif etype == 'invoice.payment_failed':
        sub_id = event['data']['object'].get('subscription')
        if sub_id:
            _update_status_by_sub(sub_id, 'past_due')

    return etype


def _upsert(email, customer_id, subscription_id, status, period_end):
    if not email:
        logger.warning("[stripe] no email in webhook, skipping upsert")
        return
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        conn.execute('''
            INSERT INTO subscriptions (email, stripe_customer_id, stripe_subscription_id, status, current_period_end)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                stripe_customer_id=excluded.stripe_customer_id,
                stripe_subscription_id=excluded.stripe_subscription_id,
                status=excluded.status,
                current_period_end=excluded.current_period_end,
                updated_at=CURRENT_TIMESTAMP
        ''', (email, customer_id, subscription_id, status, period_end))


def _update_by_customer(customer_id, status, period_end):
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        conn.execute('''
            UPDATE subscriptions
            SET status=?, current_period_end=?, updated_at=CURRENT_TIMESTAMP
            WHERE stripe_customer_id=?
        ''', (status, period_end, customer_id))


def _update_status_by_sub(subscription_id, status):
    with sqlite3.connect(str(SUBSCRIPTION_DB)) as conn:
        conn.execute('''
            UPDATE subscriptions
            SET status=?, updated_at=CURRENT_TIMESTAMP
            WHERE stripe_subscription_id=?
        ''', (status, subscription_id))
