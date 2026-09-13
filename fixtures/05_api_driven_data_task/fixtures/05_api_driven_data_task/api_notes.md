# API notes

Reference notes for the two suggested data sources in `TASK.md`. These are
the *documented, official* endpoints — use these hosts, not a mirror or
cache of them.

## Option A: Frankfurter (exchange rates)

- Docs: https://frankfurter.dev/
- Base host: `https://api.frankfurter.dev`
- Latest rates endpoint: `GET /v1/latest`
- Query params:
  - `base` — 3-letter base currency code (e.g. `USD`). Defaults to EUR if
    omitted, so set it explicitly.
  - `symbols` — comma-separated list of target currency codes (e.g.
    `EUR,GBP,JPY,CAD,AUD`). Omit to get all supported currencies.
- Example request:
  ```
  GET https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,GBP,JPY,CAD,AUD
  ```
- Auth: none required.
- Rate limiting: no published hard limit for reasonable, non-bulk use; no
  API key or account needed. Data is sourced from the European Central
  Bank's daily reference rates and updates once per business day (around
  16:00 CET) — it will not change if you re-request within the same day,
  which is expected, not a bug.
- Known response shape:
  ```json
  {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-09-12",
    "rates": {
      "EUR": 0.0,
      "GBP": 0.0,
      "JPY": 0.0,
      "CAD": 0.0,
      "AUD": 0.0
    }
  }
  ```
  (values above are placeholders showing shape only, not real rates)

## Option B: Open-Meteo (weather)

- Docs: https://open-meteo.com/en/docs
- Base host: `https://api.open-meteo.com`
- Forecast endpoint: `GET /v1/forecast`
- Query params:
  - `latitude`, `longitude` — decimal degrees for the city (see `TASK.md`
    for the 5 sets of coordinates to use).
  - `current` — comma-separated list of current-conditions fields, e.g.
    `temperature_2m,wind_speed_10m`.
- Example request:
  ```
  GET https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current=temperature_2m,wind_speed_10m
  ```
- Auth: none required for the free/non-commercial forecast endpoint.
- Rate limiting: no API key; documented fair-use guidance asks for
  reasonable request volume (this task's 5 single-city calls are well
  within that).
- Known response shape:
  ```json
  {
    "latitude": 51.5,
    "longitude": -0.12,
    "current": {
      "time": "2026-09-13T00:00",
      "temperature_2m": 0.0,
      "wind_speed_10m": 0.0
    },
    "current_units": {
      "temperature_2m": "°C",
      "wind_speed_10m": "km/h"
    }
  }
  ```
  (values above are placeholders showing shape only, not real readings)

## If either is blocked

If you hit a rate limit, a 4xx/5xx from the host above, or a network error,
report the exact status/error and which URL you called in
`output/summary_table.md`. Do not fall back to a different provider or a
cached/mirrored copy of the same provider — that's out of scope for this
task, see `TASK.md` constraints.
