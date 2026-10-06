"""The "subscription" checkout source — fe-user ``subscriptionCheckoutSource`` +
the ``subscription-checkout`` store (S152-08).

The fe-core cart (``vbwd_cart``, posted by the checkout island) is the single
source of the selection: one PLAN item, TOKEN_BUNDLE and ADD_ON items. A
``?tarif_plan_id`` loads that plan (``GET /api/v1/tarif-plans/<slug>``) and
replaces the cart's plan, exactly like ``loadPlan``; the new cart is handed back
to the browser as a ``data-vbwd-cart-write`` directive in the summary. The
gross total is plan + bundles + add-ons (each counted once, as the store does);
a coupon (scope ``SUBSCRIPTION``) gives the net total. Submit is
``POST /api/v1/user/checkout``.
"""
import math
from decimal import Decimal
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CORE_CART_KEY,
    CheckoutRouteContext,
    CheckoutSource,
    CheckoutSummary,
)
from plugins.theme_checkout.theme_checkout.coupon import price_coupon
from plugins.theme_checkout.theme_checkout.price_display import price_display_view
from plugins.theme_cms.theme_cms.components.pricing import format_money

from .billing_period import summary_period_label
from .subscription_api import SubscriptionApi

SUBSCRIPTION_SOURCE_ID = "subscription"
SUBSCRIPTION_CART_TYPE = "subscription"
SUMMARY_TEMPLATE = "subscription/checkout_summary.html.j2"
COUPON_SCOPE = "SUBSCRIPTION"
PLAN_ITEM_TYPE = "PLAN"
TOKEN_BUNDLE_ITEM_TYPE = "TOKEN_BUNDLE"
ADD_ON_ITEM_TYPE = "ADD_ON"
NO_ITEMS_SELECTED = "No items selected"
BAD_REQUEST = 400
ZERO = Decimal("0")

CartItem = Mapping[str, Any]
ApiFactory = Callable[[ThemeRequest], Any]


def matches_subscription(context: CheckoutRouteContext) -> bool:
    """A plan checkout, the bot-draft cart, or an explicit subscription cart."""
    return (
        bool(context.plan_slug)
        or context.cart_type == SUBSCRIPTION_CART_TYPE
        or context.source == SUBSCRIPTION_SOURCE_ID
    )


def _number(raw: Any) -> Optional[float]:
    """The store's ``toNumber``: a finite number, else ``None``."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def plan_cart_item(raw_plan: Mapping[str, Any], slug: str) -> Dict[str, Any]:
    """The PLAN cart item ``loadPlan`` writes (``undefined`` metadata keys dropped)."""
    raw_price = raw_plan.get("price")
    # ``price`` is the Price VO with assigned taxes, else a bare number (no VO).
    price_object: Dict[str, Any] = raw_price if isinstance(raw_price, dict) else {}
    net_price = price_object.get("netto")
    if net_price is None:
        net_price = _number(raw_plan.get("net_amount", raw_plan.get("net_price")))
    gross_price = price_object.get("brutto")
    if gross_price is None:
        gross_price = _number(raw_plan.get("gross_amount", raw_plan.get("gross_price")))
    numeric_price = gross_price
    if numeric_price is None:
        numeric_price = _number(
            raw_plan.get("price_float", raw_plan.get("display_price"))
        )
    metadata = {
        "plan_id": raw_plan.get("id"),
        "slug": raw_plan.get("slug") or slug,
        "description": raw_plan.get("description"),
        "display_price": raw_plan.get("display_price"),
        "billing_period": raw_plan.get("billing_period"),
        "currency": price_object.get("currency") or raw_plan.get("currency"),
        "net_price": net_price,
        "gross_price": gross_price,
        "effective_display_mode": raw_plan.get("effective_display_mode"),
        "prices_display_mode": raw_plan.get("prices_display_mode"),
        "price_obj": price_object or None,
    }
    return {
        "type": PLAN_ITEM_TYPE,
        "id": raw_plan.get("slug") or slug,
        "name": raw_plan.get("name"),
        "price": float(numeric_price or 0),
        "quantity": 1,
        "metadata": {
            key: value for key, value in metadata.items() if value is not None
        },
    }


def _items_of(cart: List[CartItem], item_type: str) -> List[CartItem]:
    return [item for item in cart if item.get("type") == item_type]


def _items_of_other_types(cart: List[CartItem], item_type: str) -> List[CartItem]:
    return [item for item in cart if item.get("type") != item_type]


def _plan_price(plan_item: CartItem) -> float:
    """``Number(plan.price || plan.display_price || 0)``."""
    metadata = plan_item.get("metadata") or {}
    return float(plan_item.get("price") or metadata.get("display_price") or 0)


def _order_currency(plan_item: Optional[CartItem], default_currency: str) -> str:
    metadata = (plan_item or {}).get("metadata") or {}
    price_object = metadata.get("price_obj") or {}
    return price_object.get("currency") or metadata.get("currency") or default_currency


def _plan_view(plan_item: CartItem, currency: str) -> Dict[str, Any]:
    """``PlanCheckoutSummary``'s plan row."""
    metadata = plan_item.get("metadata") or {}
    plan_gross = _plan_price(plan_item)
    gross_amount = metadata.get("gross_price")
    net_amount = metadata.get("net_price")
    period_key, period_text = summary_period_label(metadata.get("billing_period"))
    return {
        "id": metadata.get("plan_id") or plan_item.get("id"),
        "name": plan_item.get("name") or "",
        "description": metadata.get("description") or "",
        "price": price_display_view(
            plan_gross if net_amount is None else net_amount,
            plan_gross if gross_amount is None else gross_amount,
            currency,
            metadata.get("effective_display_mode"),
            metadata.get("prices_display_mode"),
        ),
        "billing_period_key": period_key,
        "billing_period_text": period_text,
    }


def _extra_view(item: CartItem, currency: str) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name") or "",
        "price_label": format_money(item.get("price"), currency),
    }


def _line_items(
    plan_item: Optional[CartItem],
    bundles: List[CartItem],
    addons: List[CartItem],
    currency: str,
) -> Tuple[Dict[str, Any], ...]:
    """The store's ``lineItems`` (subscription → token bundles → add-ons)."""
    lines: List[Dict[str, Any]] = []
    if plan_item is not None:
        metadata = plan_item.get("metadata") or {}
        lines.append(
            {
                "type": "subscription",
                "id": metadata.get("plan_id") or plan_item.get("id"),
                "name": plan_item.get("name"),
                "price": _plan_price(plan_item),
                "currency": currency,
            }
        )
    for line_type, items in (("token_bundle", bundles), ("add_on", addons)):
        lines.extend(
            {
                "type": line_type,
                "id": item.get("id"),
                "name": item.get("name"),
                "price": item.get("price"),
                "currency": currency,
            }
            for item in items
        )
    return tuple(lines)


class SubscriptionCheckout:
    """Prices and submits the subscription selection of one checkout request."""

    def __init__(
        self,
        api_factory: ApiFactory = SubscriptionApi,
        checkout_api_factory: ApiFactory = CheckoutApi,
    ) -> None:
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory

    def checkout_source(self) -> CheckoutSource:
        return CheckoutSource(
            id=SUBSCRIPTION_SOURCE_ID,
            matches=matches_subscription,
            load_summary=self.load_summary,
            submit=self.submit,
            summary_template=SUMMARY_TEMPLATE,
            cart_key=CORE_CART_KEY,
        )

    def _cart(
        self, theme_request: ThemeRequest, context: CheckoutRouteContext
    ) -> Tuple[List[CartItem], Optional[List[CartItem]]]:
        """The selection's cart, and the cart to write back when a plan was loaded."""
        cart = list(context.cart_items)
        if not context.plan_slug:
            return cart, None
        raw_plan = self._api_factory(theme_request).plan(context.plan_slug)
        plan_item = plan_cart_item(raw_plan.get("plan") or raw_plan, context.plan_slug)
        written = _items_of_other_types(cart, PLAN_ITEM_TYPE) + [plan_item]
        return written, written

    def load_summary(
        self, theme_request: ThemeRequest, context: CheckoutRouteContext
    ) -> CheckoutSummary:
        cart, cart_write = self._cart(theme_request, context)
        checkout_api = self._checkout_api_factory(theme_request)
        plans = _items_of(cart, PLAN_ITEM_TYPE)
        plan_item = plans[0] if plans else None
        bundles = _items_of(cart, TOKEN_BUNDLE_ITEM_TYPE)
        addons = _items_of(cart, ADD_ON_ITEM_TYPE)
        currency = _order_currency(plan_item, checkout_api.default_currency())
        gross_total = Decimal(str(_plan_price(plan_item) if plan_item else 0)) + sum(
            (Decimal(str(item.get("price") or 0)) for item in bundles + addons), ZERO
        )
        coupon = price_coupon(
            checkout_api, context.coupon_code, gross_total, COUPON_SCOPE
        )
        return CheckoutSummary(
            line_items=_line_items(plan_item, bundles, addons, currency),
            order_total=max(ZERO, gross_total - coupon.discount_amount),
            currency=currency,
            discount_amount=coupon.discount_amount,
            applied_coupon_code=coupon.applied_code,
            coupon_error=coupon.error,
            template_context={
                "plan": _plan_view(plan_item, currency) if plan_item else None,
                "bundles": [_extra_view(item, currency) for item in bundles],
                "addons": [_extra_view(item, currency) for item in addons],
                "cart_write": cart_write,
            },
        )

    def submit(
        self,
        theme_request: ThemeRequest,
        context: CheckoutRouteContext,
        payment_method_code: Optional[str],
    ) -> Mapping[str, Any]:
        cart, _cart_write = self._cart(theme_request, context)
        plans = _items_of(cart, PLAN_ITEM_TYPE)
        bundles = _items_of(cart, TOKEN_BUNDLE_ITEM_TYPE)
        addons = _items_of(cart, ADD_ON_ITEM_TYPE)
        if not plans and not bundles and not addons:
            raise ThemeApiError(BAD_REQUEST, NO_ITEMS_SELECTED)
        payload: Dict[str, Any] = {
            "token_bundle_ids": [item.get("id") for item in bundles],
            "add_on_ids": [item.get("id") for item in addons],
        }
        if plans:
            payload["plan_id"] = (plans[0].get("metadata") or {}).get(
                "plan_id"
            ) or plans[0].get("id")
        if payment_method_code:
            payload["payment_method_code"] = payment_method_code
        if context.coupon_code:
            payload["coupon_code"] = context.coupon_code
        result: Mapping[str, Any] = self._api_factory(theme_request).checkout(payload)
        return result
