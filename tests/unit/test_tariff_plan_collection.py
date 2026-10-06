"""S152-08 — the TariffPlanCollection CMS component, the twin of
``plugins/subscription/subscription/components/widgets/TariffPlanCollection.vue``.

Data: ``GET /api/v1/tarif-plans?currency=EUR`` (+ ``category`` in category
mode; slugs mode filters client-side), sorted by price ascending
(``useCollectionView``). Config falls back to the subscription i18n keys; an
unknown theme → ``default``. "Select plan" goes to the public checkout
(``/checkout?tarif_plan_id=``) or, with ``checkout_target: dashboard``, to
``/dashboard/checkout/<slug>``.

The current plan (S152-08): the anonymous render knows nobody; when the region
re-renders for a logged-in viewer, ``GET /api/v1/user/subscriptions/active``
(with the viewer's bearer) names the plan that is highlighted.
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest
from plugins.theme_subscription.theme_subscription.tariff_plan_collection import (
    TariffPlanCollection,
)

PLANS = [
    {
        "id": "2",
        "slug": "pro",
        "name": "Pro",
        "description": "Teams",
        "display_price": 29,
        "display_currency": "EUR",
        "billing_period": "monthly",
    },
    {
        "id": "1",
        "slug": "basic",
        "name": "Basic",
        "description": "",
        "display_price": 9,
        "net_price": 7.56,
        "gross_price": 9,
        "display_currency": "EUR",
        "billing_period": "YEARLY",
        "effective_display_mode": "netto",
        "prices_display_mode": "brutto",
    },
]


class FakeSubscriptionApi:
    def __init__(self, plans=None, active=None):
        self.plans_answer = {"plans": PLANS} if plans is None else plans
        self.active_answer = active
        self.calls = []

    def factory(self, theme_request):
        return self

    def plans(self, currency, category=None):
        self.calls.append(("plans", currency, category))
        if isinstance(self.plans_answer, Exception):
            raise self.plans_answer
        return self.plans_answer

    def active_subscription(self):
        self.calls.append(("active_subscription",))
        if isinstance(self.active_answer, Exception):
            raise self.active_answer
        return self.active_answer


def _build(config=None, api=None, user_id=None):
    api = api or FakeSubscriptionApi()
    context = TariffPlanCollection(api.factory).build_context(
        config or {}, {}, {}, FakeThemeRequest(user_id=user_id)
    )
    return context, api


def test_plans_load_in_eur_sorted_by_price_ascending():
    context, api = _build()

    assert api.calls == [("plans", "EUR", None)]
    assert context["state"] == "plans"
    assert [plan["slug"] for plan in context["plans"]] == ["basic", "pro"]


def test_category_mode_narrows_server_side_and_slugs_mode_filters():
    _context, api = _build({"category": "business"})
    slugs_context, slugs_api = _build({"source_mode": "slugs", "plan_slugs": ["pro"]})

    assert api.calls == [("plans", "EUR", "business")]
    assert slugs_api.calls == [("plans", "EUR", None)]
    assert [plan["slug"] for plan in slugs_context["plans"]] == ["pro"]


def test_a_plan_card_carries_price_period_and_its_public_checkout_link():
    context, _api = _build()
    basic = context["plans"][0]

    assert basic["price"].label == "€7.56"
    assert basic["price"].show_netto_tag is True
    assert basic["billing_period_key"] == "common.billingPeriods.year"
    assert basic["select_action"] == "/checkout"
    assert basic["search_text"] == "basic "
    assert basic["sort_key"] == 7.56


def test_the_dashboard_target_selects_into_the_dashboard_checkout():
    context, _api = _build({"checkout_target": "dashboard"})

    assert context["plans"][0]["select_action"] == "/dashboard/checkout/basic"
    assert context["select_parameter"] is None


def test_config_presentation_falls_back_to_the_i18n_keys():
    context, _api = _build({"theme": "neon", "heading": "  ", "default_view": "table"})

    assert context["theme"] == "default"
    assert context["heading"] is None
    assert context["view"] == "table"
    assert context["cta_label"] is None


def test_an_api_failure_shows_its_message_and_no_plans_is_the_empty_state():
    failed, _api = _build(api=FakeSubscriptionApi(plans=ThemeApiError(500, "boom")))
    empty, _api = _build(api=FakeSubscriptionApi(plans={"plans": []}))

    assert failed["state"] == "error" and failed["error"] == "boom"
    assert empty["state"] == "empty"


def test_the_anonymous_render_asks_for_no_subscription():
    context, api = _build()

    assert context["current_plan_slug"] is None
    assert ("active_subscription",) not in api.calls


def test_a_viewer_render_highlights_the_viewers_current_plan():
    api = FakeSubscriptionApi(active={"subscription": {"plan": {"slug": "pro"}}})

    context, _api = _build(api=api, user_id="user-1")

    assert context["current_plan_slug"] == "pro"


def test_a_viewer_without_a_subscription_has_no_current_plan():
    for answer in ({"subscription": None}, ThemeApiError(401, "expired")):
        context, _api = _build(api=FakeSubscriptionApi(active=answer), user_id="u")

        assert context["current_plan_slug"] is None
