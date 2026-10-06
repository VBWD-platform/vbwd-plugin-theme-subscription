"""S152-08 — the "subscription" checkout source, the twin of fe-user
``plugins/subscription/index.ts`` ``subscriptionCheckoutSource`` + the
``subscription-checkout`` store.

* matches ``?tarif_plan_id=…``, the bot-draft cart (``cartType: 'subscription'``)
  and ``?source=subscription``;
* the fe-core cart (``vbwd_cart``) is the single source of the selection: plan
  (one PLAN item), token bundles, add-ons; a ``?tarif_plan_id`` loads that plan
  through ``GET /api/v1/tarif-plans/<slug>`` and REPLACES the cart's plan
  (``loadPlan``) — written back to the browser with ``data-vbwd-cart-write``;
* gross = plan + bundles + add-ons; a coupon (scope ``SUBSCRIPTION``) gives the
  net total;
* submit = ``POST /api/v1/user/checkout`` with plan id, bundle / add-on ids,
  payment method and the applied coupon.
"""
from decimal import Decimal

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CORE_CART_KEY,
    CheckoutRouteContext,
)
from plugins.theme_subscription.theme_subscription.checkout_source import (
    SubscriptionCheckout,
    matches_subscription,
)

PRO_PLAN = {
    "id": "plan-uuid-1",
    "slug": "pro",
    "name": "Pro",
    "description": "For teams",
    "billing_period": "MONTHLY",
    "currency": "EUR",
    "price": {"netto": 20.0, "taxes": [], "brutto": 23.8, "currency": "EUR"},
    "effective_display_mode": "brutto",
    "prices_display_mode": "brutto",
}
BUNDLE_ITEM = {
    "type": "TOKEN_BUNDLE",
    "id": "bundle-1",
    "name": "1,000 Tokens",
    "price": 5,
    "quantity": 1,
    "metadata": {"token_amount": 1000, "currency": "EUR"},
}
ADDON_ITEM = {
    "type": "ADD_ON",
    "id": "addon-1",
    "name": "Priority Support",
    "price": 9,
    "quantity": 1,
    "metadata": {"slug": "priority-support", "currency": "EUR"},
}
STALE_PLAN_ITEM = {
    "type": "PLAN",
    "id": "basic",
    "name": "Basic",
    "price": 10,
    "quantity": 1,
    "metadata": {
        "plan_id": "plan-uuid-0",
        "slug": "basic",
        "billing_period": "monthly",
    },
}


class FakeSubscriptionApi:
    def __init__(self, plan=PRO_PLAN, checkout_result=None):
        self.plan_answer = plan
        self.checkout_result = checkout_result or {
            "invoice": {"id": "inv-1", "status": "PENDING"},
            "subscription": {"id": "sub-1", "status": "PENDING"},
        }
        self.calls = []

    def factory(self, theme_request):
        return self

    def plan(self, slug):
        self.calls.append(("plan", slug))
        if isinstance(self.plan_answer, Exception):
            raise self.plan_answer
        return self.plan_answer

    def checkout(self, payload):
        self.calls.append(("checkout", payload))
        if isinstance(self.checkout_result, Exception):
            raise self.checkout_result
        return self.checkout_result


def _source(subscription_api=None, checkout_api=None):
    subscription_api = subscription_api or FakeSubscriptionApi()
    checkout_api = checkout_api or FakeCheckoutApi(default_currency="EUR")
    return (
        SubscriptionCheckout(subscription_api.factory, checkout_api.factory),
        subscription_api,
        checkout_api,
    )


@pytest.mark.parametrize(
    "context, expected",
    [
        (CheckoutRouteContext(plan_slug="pro"), True),
        (CheckoutRouteContext(cart_type="subscription", is_cart=True), True),
        (CheckoutRouteContext(source="subscription"), True),
        (CheckoutRouteContext(source="shop"), False),
        (CheckoutRouteContext(), False),
    ],
)
def test_matches_like_the_spa_source(context, expected):
    assert matches_subscription(context) is expected


def test_the_source_checks_out_the_core_cart():
    source = _source()[0].checkout_source()

    assert source.id == "subscription"
    assert source.cart_key == CORE_CART_KEY
    assert source.summary_template == "subscription/checkout_summary.html.j2"


def test_a_plan_slug_loads_the_plan_and_replaces_the_carts_plan():
    checkout, subscription_api, _api = _source()
    context = CheckoutRouteContext(
        plan_slug="pro", cart_items=(STALE_PLAN_ITEM, BUNDLE_ITEM)
    )

    summary = checkout.load_summary(FakeThemeRequest(), context)

    assert subscription_api.calls == [("plan", "pro")]
    cart_write = summary.template_context["cart_write"]
    assert [item["type"] for item in cart_write] == ["TOKEN_BUNDLE", "PLAN"]
    plan_item = cart_write[1]
    assert plan_item == {
        "type": "PLAN",
        "id": "pro",
        "name": "Pro",
        "price": 23.8,
        "quantity": 1,
        "metadata": {
            "plan_id": "plan-uuid-1",
            "slug": "pro",
            "description": "For teams",
            "billing_period": "MONTHLY",
            "currency": "EUR",
            "net_price": 20.0,
            "gross_price": 23.8,
            "effective_display_mode": "brutto",
            "prices_display_mode": "brutto",
            "price_obj": PRO_PLAN["price"],
        },
    }


def test_the_total_is_plan_plus_bundles_plus_addons():
    checkout, _subscription_api, _api = _source()
    context = CheckoutRouteContext(
        plan_slug="pro", cart_items=(BUNDLE_ITEM, ADDON_ITEM)
    )

    summary = checkout.load_summary(FakeThemeRequest(), context)

    assert summary.order_total == Decimal("37.8")
    assert summary.currency == "EUR"
    assert [line["type"] for line in summary.line_items] == [
        "subscription",
        "token_bundle",
        "add_on",
    ]
    view = summary.template_context
    assert view["plan"]["name"] == "Pro"
    assert view["plan"]["price"].label == "€23.80"
    assert view["plan"]["billing_period_key"] == "common.billingPeriods.month"
    assert [bundle["price_label"] for bundle in view["bundles"]] == ["€5.00"]
    assert [addon["name"] for addon in view["addons"]] == ["Priority Support"]


def test_a_cart_without_a_plan_slug_uses_the_carts_plan_and_writes_nothing():
    checkout, subscription_api, _api = _source()
    context = CheckoutRouteContext(
        source="subscription", cart_items=(STALE_PLAN_ITEM, BUNDLE_ITEM)
    )

    summary = checkout.load_summary(FakeThemeRequest(), context)

    assert subscription_api.calls == []
    assert summary.template_context["cart_write"] is None
    assert summary.template_context["plan"]["name"] == "Basic"
    assert summary.order_total == Decimal("15")


def test_an_unknown_plan_is_the_checkout_error():
    checkout, _subscription_api, _api = _source(
        FakeSubscriptionApi(plan=ThemeApiError(404, "Plan not found"))
    )

    with pytest.raises(ThemeApiError) as raised:
        checkout.load_summary(FakeThemeRequest(), CheckoutRouteContext(plan_slug="x"))

    assert raised.value.message == "Plan not found"


def test_a_valid_coupon_reduces_the_total():
    checkout_api = FakeCheckoutApi(
        default_currency="EUR",
        validate_coupon={"valid": True, "discount_amount": "4.76"},
    )
    checkout, _subscription_api, _api = _source(checkout_api=checkout_api)
    context = CheckoutRouteContext(plan_slug="pro", coupon_code="SUMMER2026")

    summary = checkout.load_summary(FakeThemeRequest(), context)

    assert summary.order_total == Decimal("19.04")
    assert summary.discount_amount == Decimal("4.76")
    assert summary.applied_coupon_code == "SUMMER2026"
    assert checkout_api.called("validate_coupon") == [
        ("validate_coupon", "SUMMER2026", 23.8, "SUBSCRIPTION")
    ]


def test_submit_posts_the_selection_to_user_checkout():
    checkout, subscription_api, _api = _source()
    context = CheckoutRouteContext(
        plan_slug="pro",
        cart_items=(BUNDLE_ITEM, ADDON_ITEM),
        coupon_code="SUMMER2026",
    )

    result = checkout.submit(FakeThemeRequest(), context, "invoice")

    assert result["invoice"]["id"] == "inv-1"
    assert subscription_api.calls[-1] == (
        "checkout",
        {
            "token_bundle_ids": ["bundle-1"],
            "add_on_ids": ["addon-1"],
            "plan_id": "plan-uuid-1",
            "payment_method_code": "invoice",
            "coupon_code": "SUMMER2026",
        },
    )


def test_submit_with_nothing_selected_is_the_spa_error():
    checkout, subscription_api, _api = _source()

    with pytest.raises(ThemeApiError) as raised:
        checkout.submit(
            FakeThemeRequest(), CheckoutRouteContext(source="subscription"), None
        )

    assert raised.value.message == "No items selected"
    assert subscription_api.calls == []


def test_a_backend_refusal_carries_its_message_to_the_buyer():
    checkout, _subscription_api, _api = _source(
        FakeSubscriptionApi(checkout_result=ThemeApiError(400, "Plan is not active"))
    )

    with pytest.raises(ThemeApiError) as raised:
        checkout.submit(FakeThemeRequest(), CheckoutRouteContext(plan_slug="pro"), None)

    assert raised.value.message == "Plan is not active"
