"""Billing-period labels — the two ``formatBillingPeriod`` helpers of the SPA.

``PlanCheckoutSummary`` maps the exact stored value (incl. upper-case enum
names) and lower-cases anything else; ``TariffPlanCollection`` maps the
lower-cased value and keeps anything else verbatim. Both default to "month".
A label is a translation key, or the literal text when no key applies.
"""
from typing import Optional, Tuple

MONTH_KEY = "common.billingPeriods.month"
YEAR_KEY = "common.billingPeriods.year"
WEEK_KEY = "common.billingPeriods.week"
DEFAULT_PERIOD_KEY = MONTH_KEY
COLLECTION_PERIOD_KEYS = {
    "monthly": MONTH_KEY,
    "yearly": YEAR_KEY,
    "annual": YEAR_KEY,
    "weekly": WEEK_KEY,
}
SUMMARY_PERIOD_KEYS = {
    **COLLECTION_PERIOD_KEYS,
    "MONTHLY": MONTH_KEY,
    "YEARLY": YEAR_KEY,
}

# (translation key or None, literal text used when there is no key)
PeriodLabel = Tuple[Optional[str], str]


def summary_period_label(period: Optional[str]) -> PeriodLabel:
    if not period:
        return DEFAULT_PERIOD_KEY, ""
    key = SUMMARY_PERIOD_KEYS.get(period)
    return key, "" if key else period.lower()


def collection_period_label(period: Optional[str]) -> PeriodLabel:
    if not period:
        return DEFAULT_PERIOD_KEY, ""
    key = COLLECTION_PERIOD_KEYS.get(period.lower())
    return key, "" if key else period
