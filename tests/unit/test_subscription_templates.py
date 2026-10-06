"""S152-08 — theme_subscription markup keeps the SPA's DOM contract (D2).

* ``subscription/checkout_summary.html.j2`` = ``PlanCheckoutSummary.vue``
  (``plan-name``, ``plan-price`` = PriceDisplay + "/<period>", description,
  ``summary-token-bundle`` / ``summary-add-on`` rows) plus the cart write-back
  directive when the plan came from ``?tarif_plan_id``;
* ``subscription/components/tariff_plan_collection.html.j2`` =
  ``TariffPlanCollection.vue`` + fe-user ``CollectionToolbar.vue`` (cards and
  table views, ``select-plan-<slug>``), its plans inside a personalised region.
"""
import json
import re

import pytest

from plugins.theme.theme.viewer import ANONYMOUS_VIEWER
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutRouteContext,
)
from plugins.theme_subscription.tests.unit.template_harness import render, theme_plugin
from plugins.theme_subscription.tests.unit.test_checkout_source import (
    ADDON_ITEM,
    BUNDLE_ITEM,
    FakeSubscriptionApi as FakeCheckoutSubscriptionApi,
)
from plugins.theme_subscription.tests.unit.test_tariff_plan_collection import (
    FakeSubscriptionApi as FakeCollectionApi,
)
from plugins.theme_subscription.theme_subscription.checkout_source import (
    SubscriptionCheckout,
)
from plugins.theme_subscription.theme_subscription.tariff_plan_collection import (
    TariffPlanCollection,
)

SUMMARY = "subscription/checkout_summary.html.j2"
COLLECTION = "subscription/components/tariff_plan_collection.html.j2"


@pytest.fixture(scope="module")
def plugin():
    return theme_plugin()


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _testid(html, testid):
    return re.search(rf'<[^>]*data-testid="{re.escape(testid)}"[^>]*>', html)


def _summary_html(plugin, context):
    checkout = SubscriptionCheckout(
        FakeCheckoutSubscriptionApi().factory,
        FakeCheckoutApi(default_currency="EUR").factory,
    )
    summary = checkout.load_summary(FakeThemeRequest(), context)
    return render(
        plugin,
        SUMMARY,
        {"summary": {"line_items": summary.line_items, **summary.template_context}},
    )


def test_the_summary_shows_the_plan_like_plan_checkout_summary(plugin):
    html = _summary_html(
        plugin,
        CheckoutRouteContext(plan_slug="pro", cart_items=(BUNDLE_ITEM, ADDON_ITEM)),
    )

    assert re.search(r'<span data-testid="plan-name">Pro</span>', html)
    assert re.search(
        r'<span data-testid="plan-price"><span class="price-display">'
        r'<span class="price-display__amount" data-testid="price-amount">€23\.80</span>'
        r"</span>/month</span>",
        html,
    )
    assert '<p class="plan-description">For teams</p>' in html
    assert re.search(
        r'<div class="plan-row addon-row" data-testid="summary-token-bundle">'
        r"<span>1,000 Tokens</span><span>€5\.00</span></div>",
        html,
    )
    assert _testid(html, "summary-add-on")


def test_a_loaded_plan_is_written_back_into_the_fe_core_cart(plugin):
    html = _summary_html(plugin, CheckoutRouteContext(plan_slug="pro"))

    directive = re.search(
        r'<script type="application/json" data-vbwd-cart-write="vbwd_cart">(.*?)</script>',
        html,
    )
    assert directive is not None
    assert [item["id"] for item in json.loads(directive.group(1))] == ["pro"]


def test_a_cart_checkout_writes_nothing_back(plugin):
    html = _summary_html(
        plugin,
        CheckoutRouteContext(source="subscription", cart_items=(BUNDLE_ITEM,)),
    )

    assert "data-vbwd-cart-write" not in html
    assert not _testid(html, "plan-name")


def _collection_html(plugin, config=None, api=None, user_id=None, viewer=None):
    context = TariffPlanCollection((api or FakeCollectionApi()).factory).build_context(
        config or {}, {}, {}, FakeThemeRequest(user_id=user_id)
    )
    return render(plugin, COLLECTION, {"component_context": context}, viewer=viewer)


def test_the_collection_renders_the_header_toolbar_and_both_views(plugin):
    html = _collection_html(plugin, {"widget_slug": "plans"})

    assert '<div class="tariff-plan-collection tariff-plan-collection--default"' in html
    assert re.search(
        r'data-testid="tariff-plan-collection-heading">Select a Plan<', html
    )
    assert re.search(
        r'data-testid="tariff-plan-collection-subtitle">Choose the plan that fits you best<',
        html,
    )
    for testid in (
        "collection-search",
        "collection-sort-toggle",
        "collection-view-cards",
        "collection-view-table",
        "tariff-plan-grid",
        "tariff-plan-table",
        "tariff-plan-card-basic",
        "tariff-plan-row-pro",
    ):
        assert _testid(html, testid), testid
    assert 'placeholder="Search"' in html
    assert re.search(r'Sort by price\s*<span aria-hidden="true"[^>]*>↑</span>', html)


def test_select_plan_submits_to_the_public_checkout(plugin):
    html = _collection_html(plugin, {"widget_slug": "plans"})

    form = re.search(r'<form id="tariff-plan-select-plans"[^>]*>', html).group(0)
    assert 'method="get"' in form and "hidden" in form
    button = re.search(
        r'<button[^>]*data-testid="select-plan-basic"[^>]*>', html
    ).group(0)
    assert 'form="tariff-plan-select-plans"' in button
    assert 'formaction="/checkout"' in button
    assert 'name="tarif_plan_id" value="basic"' in button
    assert re.search(r'data-testid="select-plan-basic"[^>]*>Select Plan<', html)


def test_the_default_view_decides_which_view_is_visible(plugin):
    cards = _collection_html(plugin)
    table = _collection_html(plugin, {"default_view": "table"})

    assert (
        re.search(r'data-testid="tariff-plan-grid"[^>]*>', cards)
        .group(0)
        .count("hidden")
        == 0
    )
    assert "hidden" in re.search(
        r'<div class="tariff-plan-collection__table-wrapper"[^>]*>', cards
    ).group(0)
    assert "hidden" in re.search(r'data-testid="tariff-plan-grid"[^>]*>', table).group(
        0
    )


def test_states_error_and_empty(plugin):
    from plugins.theme.theme.theme_api import ThemeApiError

    failed = _collection_html(
        plugin, api=FakeCollectionApi(plans=ThemeApiError(500, "boom"))
    )
    empty = _collection_html(plugin, api=FakeCollectionApi(plans={"plans": []}))

    assert re.search(r'data-testid="tariff-plan-error">\s*<p>boom</p>', failed)
    assert re.search(
        r'data-testid="tariff-plan-empty">\s*<p>No plans available at this time\.</p>',
        empty,
    )
    assert not _testid(empty, "collection-search")


def test_featured_plan_badge_image_and_features(plugin):
    html = _collection_html(
        plugin,
        {
            "highlight_slug": "pro",
            "highlight_badge": "Best",
            "image_url": "/i.png",
            "features": ["A", " "],
        },
    )

    assert 'class="tariff-plan-card tariff-plan-card--featured"' in html
    assert re.search(r'data-testid="tariff-plan-badge">\s*Best\s*<', html)
    assert html.count('data-testid="tariff-plan-image"') == 2
    assert html.count('<li class="tariff-plan-card__feature">') == 2


def test_the_plans_are_a_personalised_region_and_the_current_plan_is_marked(plugin):
    from plugins.theme.theme.viewer import Viewer

    anonymous = _collection_html(plugin, viewer=ANONYMOUS_VIEWER)
    viewer_html = _collection_html(
        plugin,
        api=FakeCollectionApi(active={"subscription": {"plan": {"slug": "pro"}}}),
        user_id="user-1",
        viewer=Viewer(user_id="user-1", access_level_slugs=frozenset(), permissions=()),
    )

    assert 'data-vbwd-region="r1"' in anonymous
    assert "tariff-plan-card--current" not in anonymous
    assert re.search(
        r'class="tariff-plan-card tariff-plan-card--current"[^>]*data-testid="tariff-plan-card-pro"',
        viewer_html,
    )
