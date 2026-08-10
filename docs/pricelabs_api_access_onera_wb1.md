# PriceLabs API Access for Onera and WB1

This guide is for any agent or script that needs to access the PriceLabs endpoints used by this repo and reconstruct the `pl_daily` rows for:

- `onera`
- `wb1` (`Onera Wimberley`; if someone says "wmb", they likely mean this property key)

The goal is to build rows with this shape:

```text
Listing ID | PMS Name | Date | Units | No. Booked | No. Blocked | blocking_units | Bookable Units | nightly_revenue | Vacant Units
```

These fields do **not** come from a single PriceLabs endpoint. In this repo, they are assembled from:

1. PriceLabs `listing_prices`
2. PriceLabs `reservation_data`
3. PriceLabs `listings/{listing_id}/overrides`
4. Local listing metadata from `config/properties.yaml`

## Authentication

The API configuration lives in `rates/config.py`.

- Base URL default: `https://api.pricelabs.co/v1`
- Required env var: `PRICELABS_API_KEY`
- Optional env var: `API_BASE_URL`

Send these headers on every request:

```http
X-API-Key: <PRICELABS_API_KEY>
Content-Type: application/json
```

There is already a wrapper class in `rates/api_client.py` called `PriceLabsAPI`.

## Endpoints Used by This Repo

### 1. Get all listings

```http
GET /v1/listings
```

Full URL:

```text
https://api.pricelabs.co/v1/listings
```

Purpose:

- discover available listing IDs
- inspect listing metadata returned by PriceLabs

Repo reference:

- `rates/api_client.py` -> `PriceLabsAPI.get_listings()`

### 2. Get daily listing price and availability

```http
POST /v1/listing_prices
```

Full URL:

```text
https://api.pricelabs.co/v1/listing_prices
```

Request body:

```json
{
  "listings": [
    {
      "id": "316005___633306",
      "pms": "cloudbeds",
      "dateFrom": "2022-01-01",
      "dateTo": "2022-01-31"
    }
  ]
}
```

Purpose:

- get daily `price`
- get daily `unbookable`
- get daily `booking_status`

Repo references:

- `rates/api_client.py` -> `PriceLabsAPI.get_listing_daily_data()`
- `scripts/generate_pl_daily_comprehensive.py` -> `get_daily_data_for_listing()`

Relevant response fields used by this repo:

- `date`
- `price`
- `unbookable`
- `booking_status`

Important:

- this repo uses `unbookable` to determine blocked status
- this repo does **not** trust `booking_status` alone to calculate `No. Booked`
- `No. Booked` is calculated from `reservation_data`

### 3. Get date-specific overrides

```http
GET /v1/listings/{listing_id}/overrides
```

Example:

```http
GET /v1/listings/316005___633306/overrides?pms=cloudbeds
```

Full URL example:

```text
https://api.pricelabs.co/v1/listings/316005___633306/overrides?pms=cloudbeds
```

Purpose:

- get override prices by date
- use override price instead of default daily price when present

Repo references:

- `rates/api_client.py` -> `PriceLabsAPI.get_listing_overrides()`
- `scripts/generate_pl_daily_comprehensive.py` -> `get_listing_overrides()`

Used for:

- `nightly_revenue` in this repo's `pl_daily` generation

Important:

- in this repo, `nightly_revenue` is effectively the override price or listing price
- it is not actual realized accounting revenue

### 4. Get reservations

```http
GET /v1/reservation_data
```

Example:

```http
GET /v1/reservation_data?pms=cloudbeds&start_date=2022-01-01&end_date=2022-01-31&limit=100&offset=0
```

Full URL example:

```text
https://api.pricelabs.co/v1/reservation_data?pms=cloudbeds&start_date=2022-01-01&end_date=2022-01-31&limit=100&offset=0
```

Purpose:

- retrieve reservation rows
- compute `No. Booked` per listing per date

Repo reference:

- `scripts/generate_pl_daily_comprehensive.py` -> `fetch_all_reservations()`

Important pagination rule:

- keep paging with `offset += limit`
- stop when a page returns fewer than `limit` rows

Relevant fields expected by this repo:

- `listing_id`
- `check_in`
- `check_out`
- `booking_status`

Only rows where `booking_status == "booked"` are counted for `No. Booked`.

## Property Context

Both target properties use:

- `pms: cloudbeds`

That means all `listing_prices`, `overrides`, and `reservation_data` requests for these properties should pass `pms=cloudbeds`.

### `onera`

Property metadata from `config/properties.yaml`:

- property key: `onera`
- display name: `Onera`
- PMS: `cloudbeds`
- total units: `38`

Listings:

| Listing Name | Listing ID | Units |
|---|---|---:|
| Cocoon | `203812___362535` | 1 |
| Walnut House | `203812___364773` | 1 |
| Spyglass | `203812___364776` | 1 |
| Live Oak Lodge | `203812___364778` | 1 |
| Lantana Dome | `203812___364779` | 1 |
| Sage Safari | `203812___364780` | 1 |
| Monarch | `203812___364781` | 1 |
| Buckeye Bungalow | `203812___364782` | 1 |
| Cedar Haus | `203812___490007` | 1 |
| Juniper Haus | `203812___490024` | 1 |
| Pecan Haus | `203812___528745` | 1 |
| Bluebonnet | `203812___634080` | 1 |
| Great Lodge | `203812___643757` | 1 |
| Great Lodge: King Room | `203812___643775` | 6 |
| Great Lodge: King Room (Accessible) | `203812___657152` | 2 |
| Cypress Lodge \| Sleeps 2 | `203812___655826` | 2 |
| Cypress Lodge \| Sleeps 4 | `203812___643762` | 2 |
| Cypress Lodge \| Sleeps 6 | `203812___655827` | 2 |
| Diamond | `203812___643771` | 3 |
| Monolith | `203812___643773` | 2 |
| Post Oak | `203812___643760` | 1 |
| Quonset | `203812___643764` | 2 |
| Spiral | `203812___643772` | 1 |
| Winecup | `203812___643766` | 2 |

Notes:

- Some listings omit `units` in config; in this repo that implies a default of `1`.
- `onera` is a combined property built from the old fb1 and fb2 listing sets.

### `wb1`

Property metadata from `config/properties.yaml`:

- property key: `wb1`
- display name: `Onera Wimberley`
- PMS: `cloudbeds`
- total units: `28`

Listings:

| Listing Name | Listing ID | Units |
|---|---|---:|
| Greenhouse | `316005___633306` | 9 |
| Greenhouse ADA | `316005___633307` | 1 |
| Spyglass | `316005___633310` | 5 |
| Spyglass ADA | `316005___633311` | 1 |
| Greenhouse Pet | `316005___633308` | 6 |
| Spyglass Pet | `316005___633312` | 6 |

Important sample mapping:

- the sample listing ID `316005___633306` belongs to `wb1`
- its listing name is `Greenhouse`
- its configured unit count is `9`
- its PMS is `cloudbeds`

## How This Repo Builds `pl_daily`

The authoritative implementation is in:

- `scripts/generate_pl_daily_comprehensive.py`

For each listing and date, the repo does this:

1. Load `units` from `config/properties.yaml`
2. Call `listing_prices`
3. Call `overrides`
4. Pull all `reservation_data` rows for the PMS and date range
5. Count overlapping reservations for the listing/date
6. Build derived columns

### Column-by-column mapping

| Column | Source |
|---|---|
| `Listing ID` | `config/properties.yaml` -> `listings[].id` |
| `PMS Name` | `config/properties.yaml` -> property `pms` |
| `Date` | local loop date formatted as `YYYY-MM-DDT00:00:00.000000` |
| `Units` | `config/properties.yaml` -> `listings[].units`, default `1` |
| `No. Booked` | count of overlapping booked reservations from `reservation_data` |
| `No. Blocked` | `1` if `listing_prices.unbookable` else `0` |
| `blocking_units` | `No. Blocked * Units` |
| `Bookable Units` | `Units - No. Blocked` |
| `nightly_revenue` | override price if present, else `listing_prices.price` |
| `Vacant Units` | `max(Units - No. Booked - No. Blocked, 0)` |

### Booking count logic

This repo counts a reservation for date `D` when:

```text
check_in <= D < check_out
```

and:

```text
booking_status == "booked"
```

### Blocked logic

This repo maps:

```text
unbookable -> No. Blocked
```

Specifically:

```text
No. Blocked = 1 if unbookable else 0
```

That means:

- `No. Blocked` is treated as a listing-level blocked flag in this implementation
- `blocking_units` expands that to full unit impact by multiplying by `Units`

If you see a row like:

```text
316005___633306 | cloudbeds | 2022-01-01 | 9 | 0 | 9 | 9 | 0 | 0 | 0
```

be careful: the repo code would normally produce:

- `No. Blocked = 1`
- `blocking_units = 9`

So if another source shows `No. Blocked = 9`, that source is using a different convention than this repo.

## Recommended Request Pattern

For either `onera` or `wb1`:

1. Read the property's listing IDs and units from `config/properties.yaml`
2. Use `pms=cloudbeds`
3. Call `reservation_data` once for the property date range
4. Call `listing_prices` per listing for the date range
5. Call `overrides` per listing for the date range
6. Join those results locally

For small scripts, this is enough.

For larger backfills, follow the repo's throttling behavior.

## Rate Limiting Behavior in This Repo

The generator script applies a fixed pre-request delay:

- `REQUEST_DELAY_SECONDS = 1.2`

If the API returns `429`:

- wait for `Retry-After` header
- default to `90` seconds if missing
- retry the request

See:

- `scripts/generate_pl_daily_comprehensive.py`

## Minimal Python Example for `wb1`

This example shows how to access the endpoints for the sample `wb1` listing `316005___633306`.

```python
import os
import requests

API_KEY = os.environ["PRICELABS_API_KEY"]
BASE_URL = os.getenv("API_BASE_URL", "https://api.pricelabs.co/v1")
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

listing_id = "316005___633306"
pms = "cloudbeds"
units = 9
start_date = "2022-01-01"
end_date = "2022-01-31"

# 1) listing_prices
listing_prices_resp = requests.post(
    f"{BASE_URL}/listing_prices",
    headers=HEADERS,
    json={
        "listings": [
            {
                "id": listing_id,
                "pms": pms,
                "dateFrom": start_date,
                "dateTo": end_date,
            }
        ]
    },
    timeout=60,
)
listing_prices_resp.raise_for_status()
listing_prices_data = listing_prices_resp.json()
daily_by_date = {
    row["date"]: row
    for row in listing_prices_data[0].get("data", [])
}

# 2) overrides
overrides_resp = requests.get(
    f"{BASE_URL}/listings/{listing_id}/overrides",
    headers=HEADERS,
    params={"pms": pms},
    timeout=60,
)
overrides_resp.raise_for_status()
override_by_date = {
    row["date"]: float(row["price"])
    for row in overrides_resp.json().get("overrides", [])
}

# 3) reservation_data
reservations = []
limit = 100
offset = 0

while True:
    reservations_resp = requests.get(
        f"{BASE_URL}/reservation_data",
        headers=HEADERS,
        params={
            "pms": pms,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset,
        },
        timeout=60,
    )
    reservations_resp.raise_for_status()
    batch = reservations_resp.json().get("data", [])
    reservations.extend(batch)
    if len(batch) < limit:
        break
    offset += limit

listing_reservations = [
    row for row in reservations
    if str(row.get("listing_id")) == listing_id
    and row.get("booking_status") == "booked"
]

date_str = "2022-01-01"
daily_info = daily_by_date.get(date_str, {})

booking_count = sum(
    1
    for row in listing_reservations
    if row["check_in"] <= date_str < row["check_out"]
)
blocking_count = 1 if daily_info.get("unbookable", 0) else 0
nightly_revenue = override_by_date.get(date_str, daily_info.get("price", 0))
vacant_units = max(units - booking_count - blocking_count, 0)

pl_daily_row = {
    "Listing ID": listing_id,
    "PMS Name": pms,
    "Date": f"{date_str}T00:00:00.000000",
    "Units": units,
    "No. Booked": booking_count,
    "No. Blocked": blocking_count,
    "blocking_units": blocking_count * units,
    "Bookable Units": units - blocking_count,
    "nightly_revenue": nightly_revenue,
    "Vacant Units": vacant_units,
}

print(pl_daily_row)
```

## Best Repo Files to Read First

If another agent needs the exact implementation details, start here:

1. `rates/config.py`
2. `rates/api_client.py`
3. `scripts/generate_pl_daily_comprehensive.py`
4. `config/properties.yaml`
5. `src/pricing_engine/dataloader.py`

## One-line Summary

To reconstruct `pl_daily` for `onera` or `wb1`, use `pms=cloudbeds`, read listing IDs and units from `config/properties.yaml`, fetch `listing_prices`, `reservation_data`, and `listings/{listing_id}/overrides` from PriceLabs, then apply the local formulas from `scripts/generate_pl_daily_comprehensive.py`.
