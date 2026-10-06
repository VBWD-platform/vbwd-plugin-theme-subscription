"""The TariffPlanCollection CMS component — ``TariffPlanCollection.vue`` (S152-08).

Plans come from ``GET /api/v1/tarif-plans?currency=EUR`` (``category`` narrows
server-side in category mode; slugs mode filters here), price-ascending as
``useCollectionView`` starts. Quick search, the sort toggle and the view switch
are client-only (``tariff_plan_collection_runtime.js``). "Select plan" submits
to the public checkout (``?tarif_plan_id=``) or the dashboard checkout.

Current plan: the component's plans render inside a personalised region; when
the region re-renders for a logged-in viewer, ``GET
/api/v1/user/subscriptions/active`` (with the viewer's bearer) names the plan to
highlight. The anonymous render never asks.
"""
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.price_display import price_display_view
from plugins.theme_cms.theme_cms.markup import style_text

from .billing_period import collection_period_label
from .subscription_api import SubscriptionApi

PLANS_CURRENCY = "EUR"
ALLOWED_THEMES = ("default", "light", "dark", "teal", "indigo", "emerald")
DEFAULT_THEME = "default"
SLUGS_MODE = "slugs"
CARDS_VIEW = "cards"
DASHBOARD_TARGET = "dashboard"
PUBLIC_CHECKOUT_PATH = "/checkout"
DASHBOARD_CHECKOUT_PATH = "/dashboard/checkout/{slug}"
PLAN_PARAMETER = "tarif_plan_id"
DEFAULT_WIDGET_SLUG = "collection"


def _text(config: Mapping[str, Any], key: str) -> Optional[str]:
    """A trimmed, non-blank string config value, else ``None`` (i18n fallback)."""
    value = config.get(key)
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _presentation(config: Mapping[str, Any]) -> Dict[str, Any]:
    theme = config.get("theme")
    features = config.get("features")
    is_dashboard = config.get("checkout_target") == DASHBOARD_TARGET
    return {
        "theme": theme if theme in ALLOWED_THEMES else DEFAULT_THEME,
        "heading": _text(config, "heading"),
        "subtitle": _text(config, "subtitle"),
        "cta_label": _text(config, "cta_label"),
        "badge": _text(config, "highlight_badge"),
        "image_url": _text(config, "image_url"),
        "features": [
            str(feature).strip()
            for feature in (features if isinstance(features, list) else [])
            if str(feature).strip()
        ],
        "view": config.get("default_view") or CARDS_VIEW,
        "form_id": f"tariff-plan-select-{config.get('widget_slug') or DEFAULT_WIDGET_SLUG}",
        "select_parameter": None if is_dashboard else PLAN_PARAMETER,
        "css": style_text(config.get("css")),
    }


def _price_basis(plan: Mapping[str, Any], net_or_gross: str) -> Any:
    value = plan.get(net_or_gross)
    return plan.get("display_price") if value is None else value


def _plan_view(plan: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    slug = plan.get("slug") or ""
    period_key, period_text = collection_period_label(plan.get("billing_period"))
    net_amount = _price_basis(plan, "net_price")
    is_dashboard = config.get("checkout_target") == DASHBOARD_TARGET
    return {
        "slug": slug,
        "name": plan.get("name") or "",
        "description": plan.get("description") or "",
        "price": price_display_view(
            net_amount,
            _price_basis(plan, "gross_price"),
            plan.get("display_currency"),
            plan.get("effective_display_mode"),
            plan.get("prices_display_mode"),
        ),
        "billing_period_key": period_key,
        "billing_period_text": period_text,
        "select_action": (
            DASHBOARD_CHECKOUT_PATH.format(slug=slug)
            if is_dashboard
            else PUBLIC_CHECKOUT_PATH
        ),
        "search_text": f"{plan.get('name') or ''} {plan.get('description') or ''}".lower(),
        "sort_key": float(net_amount or 0),
        "is_featured": bool(config.get("highlight_slug"))
        and slug == config.get("highlight_slug"),
    }


class TariffPlanCollection:
    """``build_context(widget_config, page, route_params, theme_request)``."""

    def __init__(
        self, api_factory: Callable[[ThemeRequest], Any] = SubscriptionApi
    ) -> None:
        self._api_factory = api_factory

    def build_context(
        self,
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: ThemeRequest,
    ) -> Dict[str, Any]:
        api = self._api_factory(theme_request)
        context = _presentation(widget_config)
        is_slugs_mode = widget_config.get("source_mode") == SLUGS_MODE
        category = None if is_slugs_mode else widget_config.get("category")
        try:
            plans: List[Mapping[str, Any]] = (
                api.plans(PLANS_CURRENCY, category).get("plans") or []
            )
        except ThemeApiError as load_error:
            return {
                **context,
                "state": "error",
                "error": load_error.message,
                "plans": [],
            }
        if is_slugs_mode:
            wanted = widget_config.get("plan_slugs") or []
            plans = [plan for plan in plans if plan.get("slug") in wanted]
        views = sorted(
            (_plan_view(plan, widget_config) for plan in plans),
            key=lambda view: view["sort_key"],
        )
        return {
            **context,
            "state": "plans" if views else "empty",
            "error": None,
            "plans": views,
            "current_plan_slug": self._current_plan_slug(api, theme_request),
        }

    @staticmethod
    def _current_plan_slug(api: Any, theme_request: ThemeRequest) -> Optional[str]:
        if theme_request.viewer.user_id is None:
            return None
        try:
            subscription = api.active_subscription().get("subscription") or {}
        except ThemeApiError:
            return None
        return (subscription.get("plan") or {}).get("slug")
