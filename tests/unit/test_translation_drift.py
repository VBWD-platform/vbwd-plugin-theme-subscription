"""S152-08 — theme_subscription's English catalog never drifts from the SPA's copy.

Every message a template asks for (``_('…')``) and every key the Python code
chooses is in ``translations/en.json``, with no unused entry; each equals the
SPA's English for the same key (fe-user core ``vue/src/i18n/locales/en.json`` +
``plugins/subscription/locales/en.json``). The fe-user half skips when fe-user
is not next to vbwd-backend (plugin CI).
"""
import json
import re
from pathlib import Path

import pytest

from plugins.theme.tests.catalog_contract import translated_catalog_paths
from plugins.theme_subscription.theme_subscription import billing_period
from plugins.theme_subscription.theme_subscription.plugin_paths import (
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)

FE_USER_ROOT = Path(__file__).resolve().parents[4].parent / "vbwd-fe-user"
FE_USER_CATALOGS = (
    FE_USER_ROOT / "vue" / "src" / "i18n" / "locales" / "en.json",
    FE_USER_ROOT / "plugins" / "subscription" / "locales" / "en.json",
)
CODE_CHOSEN_KEYS = set(billing_period.SUMMARY_PERIOD_KEYS.values()) | {
    billing_period.DEFAULT_PERIOD_KEY
}
TRANSLATION_CALL = re.compile(r"""_\(\s*'([A-Za-z0-9_.]+)'\s*[,)]""")


def _catalog():
    return json.loads((TRANSLATIONS_DIRECTORY / "en.json").read_text(encoding="utf-8"))


def _flatten(prefix, node):
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _flatten(f"{prefix}{key}.", value)
        else:
            yield f"{prefix}{key}", value


def _template_keys():
    keys = set()
    for template in TEMPLATES_DIRECTORY.rglob("*.j2"):
        keys.update(TRANSLATION_CALL.findall(template.read_text(encoding="utf-8")))
    return keys


def test_every_requested_message_is_in_the_catalog():
    assert (_template_keys() | CODE_CHOSEN_KEYS) - set(_catalog()) == set()


def test_the_catalog_has_no_unused_entries():
    assert set(_catalog()) - _template_keys() - CODE_CHOSEN_KEYS == set()


def test_every_entry_equals_the_spa_english():
    if not all(path.is_file() for path in FE_USER_CATALOGS):
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    spa = {}
    for path in FE_USER_CATALOGS:
        spa.update(_flatten("", json.loads(path.read_text(encoding="utf-8"))))
    drifted = {
        key: (value, spa.get(key))
        for key, value in _catalog().items()
        if value != spa.get(key)
    }

    assert not drifted, drifted


def _spa_translations(language):
    """The SPA's messages in ``language``, merged in the same order as English."""
    spa = {}
    for path in FE_USER_CATALOGS:
        localized = path.with_name(f"{language}.json")
        if localized.is_file():
            spa.update(_flatten("", json.loads(localized.read_text(encoding="utf-8"))))
    return spa


def test_every_translated_entry_equals_the_spa_translation():
    if not all(path.is_file() for path in FE_USER_CATALOGS):
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    drifted = {}
    for catalog_path in translated_catalog_paths(TRANSLATIONS_DIRECTORY):
        spa = _spa_translations(catalog_path.stem)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for key, value in catalog.items():
            if value != spa.get(key):
                drifted[f"{catalog_path.stem}:{key}"] = (value, spa.get(key))

    assert not drifted, drifted
