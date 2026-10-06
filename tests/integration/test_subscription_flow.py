"""S152-08 — theme_subscription on a real ``create_app`` (theme mode).

* ``/checkout?tarif_plan_id=<slug>`` → the island posts the fe-core cart; the
  subscription source loads the plan through the real ``/api/v1/tarif-plans``
  and writes it back into the cart; confirm with the invoice method →
  ``POST /api/v1/user/checkout`` → ``HX-Redirect`` to the confirmation, whose
  region shows the owner's PENDING invoice with the "Payment Processing" banner
  (the backend's upper-case status, compared case-insensitively — B1);
* the TariffPlanCollection widget on a CMS page lists the plans anonymously and
  marks the viewer's current plan only in the bearer re-render.
"""
import json
import re
import uuid

import pytest

from plugins.theme_checkout.tests.integration.themed_stack import (
    FE_USER_ROOT,
    RENDER,
    confirmation_page,
    contract_drift,
    contract_misses,
    ensure_euro_currency,
    ensure_invoice_payment_method,
    post_island,
    regions_html,
    submit_checkout,
)

CONFIRMATION = re.compile(r"^/checkout/confirmation\?invoice_id=([0-9a-f-]+)$")


def _testid(html, testid):
    return re.search(rf'<[^>]*data-testid="{re.escape(testid)}"[^>]*>', html)


def _plan(client, admin_headers, name="S152-08 Theme Plan"):
    ensure_euro_currency(client, admin_headers)
    slug = f"s152-08-plan-{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/admin/tarif-plans/",
        json={
            "name": name,
            "slug": slug,
            "price": 9.99,
            "billing_period": "monthly",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert created.status_code in (200, 201), created.get_json()
    return created.get_json()["plan"]


def _island_fields(plan_slug, cart="[]"):
    return {
        "source": "",
        "tarif_plan_id": plan_slug,
        "cart_type": "",
        "is_cart": "",
        "cart": cart,
    }


def test_the_plan_checkout_page_is_an_island_over_the_core_cart(client, admin_headers):
    plan = _plan(client, admin_headers)

    html = client.get(
        f"/checkout?tarif_plan_id={plan['slug']}", headers=RENDER
    ).get_data(as_text=True)

    holder = re.search(r'<div class="checkout-island"[^>]*>', html).group(0)
    assert 'data-vbwd-cart="vbwd_cart"' in holder
    assert f'"tarif_plan_id": "{plan["slug"]}"' in holder


def test_a_full_themed_subscription_checkout(client, bearer, admin_headers, cms):
    plan = _plan(client, admin_headers)
    ensure_invoice_payment_method(client, admin_headers)
    confirmation_page(cms, client)

    island = post_island(client, bearer, _island_fields(plan["slug"]))

    assert re.search(r'data-testid="plan-name">S152-08 Theme Plan<', island)
    assert _testid(island, "payment-method-invoice")
    written = json.loads(
        re.search(r'data-vbwd-cart-write="vbwd_cart">(.*?)</script>', island).group(1)
    )
    assert [(item["type"], item["id"]) for item in written] == [("PLAN", plan["slug"])]

    submitted = submit_checkout(
        client, bearer, _island_fields(plan["slug"], cart=json.dumps(written))
    )

    assert submitted.status_code == 200, submitted.get_data(as_text=True)
    invoice_id = CONFIRMATION.match(submitted.headers["HX-Redirect"]).group(1)
    confirmation = regions_html(
        client, bearer, f"/checkout/confirmation?invoice_id={invoice_id}"
    )
    assert _testid(confirmation, "invoice-details")
    assert "<h1>Payment Processing</h1>" in confirmation
    assert re.search(
        r'data-testid="line-item-row"><td>[^<]*S152-08 Theme Plan', confirmation
    )


def test_an_unknown_plan_is_the_checkout_error(client, bearer):
    island = post_island(client, bearer, _island_fields("no-such-plan-s152"))

    assert _testid(island, "checkout-error")
    assert "Plan not found" in island


def _active_plan_slug(client, bearer, admin_headers):
    ensure_euro_currency(client, admin_headers)
    active = client.get("/api/v1/user/subscriptions/active", headers=bearer).get_json()
    if active.get("subscription"):
        return active["subscription"]["plan"]["slug"]
    plan = _plan(client, admin_headers, name="S152-08 Current Plan")
    user = client.get("/api/v1/user/profile", headers=bearer).get_json()["user"]
    created = client.post(
        "/api/v1/admin/subscriptions/",
        json={"user_id": user["id"], "plan_id": plan["id"], "status": "active"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.get_json()
    return plan["slug"]


def test_the_plan_collection_marks_the_viewers_plan_only_for_the_viewer(
    client, bearer, admin_headers, cms
):
    current_slug = _active_plan_slug(client, bearer, admin_headers)
    widget = cms.vue_widget(
        "TariffPlanCollection",
        config={"source_mode": "slugs", "plan_slugs": [current_slug]},
    )
    page = cms.page_with_widgets([widget])

    anonymous = client.get(f"/{page['slug']}", headers=RENDER).get_data(as_text=True)
    personalised = regions_html(client, bearer, f"/{page['slug']}")

    assert _testid(anonymous, f"tariff-plan-card-{current_slug}")
    assert "tariff-plan-card--current" not in anonymous
    assert re.search(
        rf'class="tariff-plan-card[^"]*tariff-plan-card--current"[^>]*'
        rf'data-testid="tariff-plan-card-{re.escape(current_slug)}"',
        personalised,
    )


# ── e2e DOM contract (the themed subscription checkout specs) ────────────────

COUPON_PUBLIC = "vue/tests/e2e/checkout/coupon-public.spec.ts"
DRAFT_CHECKOUT = "plugins/checkout/tests/e2e/draft-checkout.spec.ts"
SUBSCRIPTION_CONTRACT = [
    (
        '[data-testid="order-summary"]',
        COUPON_PUBLIC,
        28,
        "island",
        r'data-testid="order-summary"',
    ),
    (
        '[data-testid="coupon-input"]',
        COUPON_PUBLIC,
        31,
        "island",
        r'data-testid="coupon-input"',
    ),
    ("'order-total'", COUPON_PUBLIC, 33, "island", r'data-testid="order-total"'),
    (
        '[data-testid="coupon-apply"]',
        COUPON_PUBLIC,
        37,
        "island",
        r'data-testid="coupon-apply"',
    ),
    (
        '[data-testid="order-discount"]',
        COUPON_PUBLIC,
        39,
        "island_discounted",
        r'data-testid="order-discount"',
    ),
    (
        '[data-testid="coupon-error"]',
        COUPON_PUBLIC,
        51,
        "island_bogus_coupon",
        r'data-testid="coupon-error"',
    ),
    (
        '[data-testid="plan-name"]',
        DRAFT_CHECKOUT,
        50,
        "island",
        r'data-testid="plan-name">S152-08 Theme Plan<',
    ),
]


def _subscription_coupon(client, admin_headers):
    discount = client.post(
        "/api/v1/admin/discounts",
        json={"name": "S152-08 Twenty", "value": 20, "scope": "SUBSCRIPTION"},
        headers=admin_headers,
    )
    assert discount.status_code == 201, discount.get_json()
    discount_body = discount.get_json()
    discount_id = (discount_body.get("discount") or discount_body)["id"]
    code = f"S15208{uuid.uuid4().hex[:6].upper()}"
    coupon = client.post(
        "/api/v1/admin/coupons",
        json={"code": code, "discount_id": discount_id},
        headers=admin_headers,
    )
    assert coupon.status_code == 201, coupon.get_json()
    return code


def test_every_subscription_spec_selector_is_in_the_themed_output(
    client, bearer, admin_headers
):
    plan = _plan(client, admin_headers)
    code = _subscription_coupon(client, admin_headers)

    def island(**coupon_fields):
        return post_island(
            client, {}, {**_island_fields(plan["slug"]), **coupon_fields}
        )

    outputs = {
        "island": island(),
        "island_discounted": island(coupon_action="apply", coupon_input=code),
        "island_bogus_coupon": island(
            coupon_action="apply", coupon_input="NOTACODE123"
        ),
    }

    assert contract_misses(SUBSCRIPTION_CONTRACT, outputs) == []


def test_the_subscription_spec_lines_still_use_these_selectors():
    if not (FE_USER_ROOT / COUPON_PUBLIC).is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")

    assert contract_drift(SUBSCRIPTION_CONTRACT) == []
