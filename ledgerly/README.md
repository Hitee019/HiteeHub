# Ledgerly

A dependency-free web app and JSON API for finding recurring subscriptions in transaction history.

## Run

```bash
python3 app.py
```

The dashboard is served on port 5000.

## API

`POST /api/detect`

```json
{
  "transactions": [
    {"merchant": "Netflix", "amount": 15.49, "date": "2026-01-05"}
  ],
  "min_occurrences": 3,
  "amount_tolerance": 0.1
}
```

The API also accepts `text/csv` requests with `merchant`, `amount`, and `date` columns. Dates must be ISO formatted (`YYYY-MM-DD`) and amounts represent money out.