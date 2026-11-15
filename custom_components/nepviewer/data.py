"""Normalize site overview values; never substitute a device for a site."""
from decimal import Decimal, InvalidOperation
import math


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def energy_kwh(production, period):
    value = number(production.get(period))
    if value is None:
        return None
    unit = str(production.get(f"{period}Unit") or "").strip().lower()
    factors = {"wh": 0.001, "kwh": 1, "mwh": 1000}
    # Observed site/overview response: yesterday=6200, yesterdayUnit=""
    # renders as 6.2 kWh in the portal. Scope this exception to yesterday.
    if not unit and period == "yesterday":
        return value / 1000
    factor = factors.get(unit)
    return value * factor if factor is not None else None


def income(overview, period):
    production = overview.get("statisticsProduction") or {}
    raw = number(production.get(f"{period}Money"))
    if raw is not None and raw != 0:
        return raw
    energy = energy_kwh(production, period)
    price = number((overview.get("selected") or {}).get("local_electric_price"))
    if energy is not None and price is not None:
        try:
            return float(Decimal(str(energy)) * Decimal(str(price)))
        except InvalidOperation:
            return None
    return raw


def site_value(site, period):
    overview = site.get("_site_overview") or {}
    return energy_kwh(overview.get("statisticsProduction") or {}, period)


def devices(site):
    overview = site.get("_site_overview") or {}
    return [d for d in overview.get("deviceList", [])
            if isinstance(d, dict) and d.get("sn")]
