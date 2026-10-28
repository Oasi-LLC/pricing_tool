"""The ONE list of lowest prices (config/batna.yaml), read the same way by all three price tools.

Source: Oasi-LLC/pricing_tool utils/batna_floors.py. Copies: price-session floors.py, five-percent-run floors.py.
Keep all three byte-identical.

    floors = parse(yaml.safe_load(text))     # refuses a list it can't read exactly (raises ValueError)
    floor_for(floors, "4140___8114", date(2026, 11, 3))  # -> 435.0, or None if the unit isn't in the list
"""
from datetime import date

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
RULE_KEYS = {"months", "start", "end", "days", "batna", "week"}
CONDITIONS = {"months", "start", "end", "days"}


def _day(v, where):
    try:
        return v if isinstance(v, date) else date.fromisoformat(str(v))
    except ValueError:
        raise ValueError(f"{where}: '{v}' is not a date like 2026-12-01")


def _rule(r, where):
    if not isinstance(r, dict) or not r:
        raise ValueError(f"{where}: a rule must be a mapping")
    unknown = set(r) - RULE_KEYS
    if unknown:
        raise ValueError(f"{where}: unknown field(s) {sorted(unknown)}")
    if ("batna" in r) == ("week" in r):
        raise ValueError(f"{where}: give exactly one of batna or week")
    out = {}
    if "batna" in r:
        out["batna"] = float(r["batna"])
        if out["batna"] <= 0:
            raise ValueError(f"{where}: batna must be above 0")
    else:
        week = r["week"]
        if not isinstance(week, list) or len(week) != 7:
            raise ValueError(f"{where}: week needs 7 prices, Mon..Sun")
        out["week"] = tuple(float(p) for p in week)
        if min(out["week"]) <= 0:
            raise ValueError(f"{where}: every week price must be above 0")
    if "months" in r:
        months = {int(m) for m in r["months"]}
        if not months or not months <= set(range(1, 13)):
            raise ValueError(f"{where}: months must be 1..12")
        out["months"] = frozenset(months)
    if "days" in r:
        days = {str(d).strip().lower()[:3] for d in r["days"]}
        if not days or not days <= set(DAYS):
            raise ValueError(f"{where}: days must be mon..sun")
        out["days"] = frozenset(DAYS.index(d) for d in days)
    if "start" in r:
        out["start"] = _day(r["start"], where)
    if "end" in r:
        out["end"] = _day(r["end"], where)
    if "start" in out and "end" in out and out["end"] < out["start"]:
        raise ValueError(f"{where}: end is before start")
    return out


def parse(cfg):
    """batna.yaml (already parsed) -> {listing_id: [rules]}. Raises ValueError on anything it can't read exactly."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("listings"), dict) or not cfg["listings"]:
        raise ValueError("batna.yaml: no 'listings'")
    out = {}
    for lid, entry in cfg["listings"].items():
        where = f"batna.yaml {lid}"
        rules = entry.get("floors") if isinstance(entry, dict) else None
        if not isinstance(rules, list) or not rules:
            raise ValueError(f"{where}: no floors")
        parsed = [_rule(r, f"{where} rule {i + 1}") for i, r in enumerate(rules)]
        if set(parsed[-1]) & CONDITIONS:
            raise ValueError(f"{where}: the last rule must have no condition, so every night has a lowest price")
        out[str(lid)] = parsed
    return out


def _fits(rule, night):
    return (("months" not in rule or night.month in rule["months"])
            and ("days" not in rule or night.weekday() in rule["days"])
            and ("start" not in rule or night >= rule["start"])
            and ("end" not in rule or night <= rule["end"]))


def floor_from_rules(rules, night):
    """Lowest price on one night (a date) from one unit's parsed rules."""
    for rule in rules:
        if _fits(rule, night):
            return rule["batna"] if "batna" in rule else rule["week"][night.weekday()]
    return None  # unreachable: parse() makes the last rule fit every night


def floor_for(floors, listing_id, night):
    """Lowest price for one unit on one night (a date). None = the unit isn't in the list."""
    rules = floors.get(str(listing_id))
    return None if rules is None else floor_from_rules(rules, night)
