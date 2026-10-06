"""Theme adapter mirroring the fe-user subscription plugin (S152-08).

Renders only when ``VBWD_FRONTEND_MODE=theme``; in the default ``vue`` mode the
Vue SPA serves every page. The subscription pages are dashboard-only, so the
adapter themes no route (D7): on enable it contributes its templates,
translations and ported stylesheet, the ``TariffPlanCollection`` CMS widget
twin (into theme_cms) and the ``subscription`` checkout source (into
theme_checkout). It talks to the backend over the public API only (D3).
"""
from typing import Optional

from flask import current_app

from vbwd.plugins.base import BasePlugin, PluginMetadata

from plugins.theme.theme.page_registry import resolve_theme_plugin
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    THEME_CHECKOUT_PLUGIN_NAME,
)
from plugins.theme_cms.theme_cms.registries import (
    THEME_CMS_PLUGIN_NAME,
    ComponentTemplate,
)
from plugins.theme_subscription.theme_subscription.checkout_source import (
    SubscriptionCheckout,
)
from plugins.theme_subscription.theme_subscription.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_subscription.theme_subscription.tariff_plan_collection import (
    TariffPlanCollection,
)

TARIFF_PLAN_COLLECTION = ComponentTemplate(
    "TariffPlanCollection",
    "subscription/components/tariff_plan_collection.html.j2",
    TariffPlanCollection().build_context,
)


class ThemeSubscriptionPlugin(BasePlugin):
    """Theme adapter mirroring the fe-user subscription plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="theme_subscription",
            version="1.0.0",
            author="VBWD Team",
            description="Theme adapter mirroring the fe-user subscription plugin.",
            dependencies=["theme>=1.0", "subscription", "theme_checkout", "theme_cms"],
        )

    def on_enable(self) -> None:
        plugin_manager = getattr(current_app, "plugin_manager")
        # Declared dependencies: enabled before this plugin (dependency order).
        components = plugin_manager.get_plugin(THEME_CMS_PLUGIN_NAME).component_registry
        if components.resolve(TARIFF_PLAN_COLLECTION.name) is None:
            components.register(TARIFF_PLAN_COLLECTION)
        plugin_manager.get_plugin(THEME_CHECKOUT_PLUGIN_NAME).source_registry.register(
            SubscriptionCheckout().checkout_source()
        )
        theme_registry = resolve_theme_plugin().theme_registry
        if TEMPLATES_DIRECTORY in theme_registry.contributed_template_paths():
            return
        theme_registry.add_contributed_template_path(TEMPLATES_DIRECTORY)
        theme_registry.add_contributed_translation_path(TRANSLATIONS_DIRECTORY)
        theme_registry.add_contributed_stylesheet_path(STYLESHEETS_DIRECTORY)

    def get_url_prefix(self) -> Optional[str]:
        # No blueprint of its own: no themed route (the pages are dashboard-only).
        return ""
