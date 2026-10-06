"""The public subscription API the fe-user plugin calls, always through core C2 (D3).

``plans`` / ``plan`` → ``GET /api/v1/tarif-plans[/<slug>]`` (``plans`` store,
``loadPlan``), ``checkout`` → ``POST /api/v1/user/checkout``
(``submitCheckout``), ``active_subscription`` →
``GET /api/v1/user/subscriptions/active`` (the viewer's current plan). The
caller's headers are forwarded; a non-2xx answer raises ``ThemeApiError``.
"""
from typing import Any, Mapping, Optional
from urllib.parse import quote

from plugins.theme.theme.theme_api import call_api
from plugins.theme.theme.theme_request import ThemeRequest

TARIF_PLANS_PATH = "/api/v1/tarif-plans"


class SubscriptionApi:
    """The subscription endpoints for one themed request."""

    def __init__(self, theme_request: ThemeRequest) -> None:
        self._theme_request = theme_request

    def plans(self, currency: str, category: Optional[str] = None) -> Any:
        query = {"currency": currency}
        if category:
            query["category"] = category
        return call_api(self._theme_request, "GET", TARIF_PLANS_PATH, query=query)

    def plan(self, slug: str) -> Any:
        return call_api(
            self._theme_request, "GET", f"{TARIF_PLANS_PATH}/{quote(slug, safe='')}"
        )

    def checkout(self, payload: Mapping[str, Any]) -> Any:
        return call_api(
            self._theme_request, "POST", "/api/v1/user/checkout", json=dict(payload)
        )

    def active_subscription(self) -> Any:
        return call_api(self._theme_request, "GET", "/api/v1/user/subscriptions/active")
