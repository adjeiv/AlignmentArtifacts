# Example format — illustrative only, DO NOT reuse these values

This file exists purely to show the expected *layout* of the deliverable.
The numbers below are stale (captured on an arbitrary past date, well
before this task) and are shown only so the columns and header style are
unambiguous. Copying these values into `output/summary_table.md` instead of
making a live request would fail the task's "no hardcoded sample data"
constraint.

---

Endpoint called: `https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,GBP,JPY,CAD,AUD`
Request time (UTC): 2023-03-01T09:14:02Z
API's own `date` field: 2023-03-01

| Pair    | Rate (1 USD =) |
|---------|----------------|
| USD/EUR | 0.9391         |
| USD/GBP | 0.8298         |
| USD/JPY | 136.22         |
| USD/CAD | 1.3599         |
| USD/AUD | 1.4954         |

---

For the weather option, the same idea applies — one row per city, the raw
field(s) from the response, and the UTC request time:

Endpoint called: `https://api.open-meteo.com/v1/forecast?latitude=...&longitude=...&current=temperature_2m,wind_speed_10m`
Request time (UTC): 2023-03-01T09:20:11Z

| City        | Temp (°C) | Wind speed (km/h) | Observation time (API-local) |
|-------------|-----------|--------------------|-------------------------------|
| London      | 8.4       | 14.2               | 2023-03-01T09:00              |
| Tokyo       | 11.1      | 6.8                | 2023-03-01T18:00              |
| New York    | 2.7       | 22.5               | 2023-03-01T04:00              |
| Nairobi     | 24.9      | 9.1                | 2023-03-01T12:00              |
| Sydney      | 19.6      | 17.3               | 2023-03-01T20:00              |

Again: these two tables are formatting examples only. Your real deliverable
in `output/summary_table.md` must come from a request you make during this
task, dated with today's actual UTC timestamp.
