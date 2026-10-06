"""S152-08 — what theme_subscription registers on enable.

No pages (the subscription pages are dashboard-only, D7); the
``TariffPlanCollection`` CMS component into theme_cms's registry (the name
fe-user ``subscription/index.ts`` registers) and the ``subscription`` checkout
source into theme_checkout's registry; its templates, translations and
stylesheets are contributed to the theme.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from plugins.theme import ThemePlugin
from plugins.theme_checkout import ThemeCheckoutPlugin
from plugins.theme_checkout.theme_checkout.checkout_sources import CheckoutRouteContext
from plugins.theme_cms import ThemeCmsPlugin
from plugins.theme_subscription import ThemeSubscriptionPlugin
from plugins.theme_subscription.theme_subscription.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)

FE_USER_SUBSCRIPTION_INDEX = (
    Path(__file__).resolve().parents[5]
    / "vbwd-fe-user"
    / "plugins"
    / "subscription"
    / "index.ts"
)


def _app(plugins):
    app = Flask(__name__)
    app.plugin_manager = SimpleNamespace(get_plugin=plugins.get)
    return app


@pytest.fixture
def enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))
    plugins = {
        "theme": ThemePlugin(),
        "theme_cms": ThemeCmsPlugin(),
        "theme_checkout": ThemeCheckoutPlugin(),
        "theme_subscription": ThemeSubscriptionPlugin(),
    }
    with _app(plugins).app_context():
        for plugin in plugins.values():
            plugin.on_enable()
        yield SimpleNamespace(**plugins)


def test_registers_no_page(enabled):
    rules = {page.rule for page in enabled.theme.page_registry.pages()}

    assert not any(
        rule.startswith(("/dashboard", "/plans", "/subscription")) for rule in rules
    )


def test_registers_the_tariff_plan_collection_component(enabled):
    component = enabled.theme_cms.component_registry.resolve("TariffPlanCollection")

    assert (
        component.template == "subscription/components/tariff_plan_collection.html.j2"
    )


def test_registers_the_subscription_checkout_source(enabled):
    source = enabled.theme_checkout.source_registry.find(
        CheckoutRouteContext(plan_slug="pro")
    )

    assert source.id == "subscription"


def test_contributes_templates_translations_and_stylesheets(enabled):
    registry = enabled.theme.theme_registry

    assert TEMPLATES_DIRECTORY in registry.contributed_template_paths()
    assert TRANSLATIONS_DIRECTORY in registry.contributed_translation_paths()
    assert STYLESHEETS_DIRECTORY in registry.contributed_stylesheet_paths()


def test_enabling_twice_registers_once(enabled):
    plugins = vars(enabled)
    with _app(plugins).app_context():
        enabled.theme_subscription.on_enable()

    registry = enabled.theme.theme_registry
    assert registry.contributed_template_paths().count(TEMPLATES_DIRECTORY) == 1


def test_the_component_name_is_the_one_fe_user_registers():
    if not FE_USER_SUBSCRIPTION_INDEX.is_file():
        pytest.skip(
            "fe-user subscription plugin is not next to vbwd-backend (plugin CI)"
        )

    assert "registerCmsVueComponent('TariffPlanCollection'" in (
        FE_USER_SUBSCRIPTION_INDEX.read_text(encoding="utf-8")
    )
