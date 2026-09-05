"""Small dependency-free web app and JSON API for subscription detection."""

import csv
import io
import json
import math
import mimetypes
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from detector import Transaction, detect_subscriptions


ROOT = Path(__file__).parent
STATIC = ROOT / "static" if (ROOT / "static").is_dir() else ROOT


def parse_transactions(payload) -> list[Transaction]:
    if not isinstance(payload, list):
        raise ValueError("transactions must be an array")

    transactions = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Transaction {index + 1} must be an object")
        merchant = item.get("merchant") or item.get("merchant_name")
        amount = item.get("amount")
        raw_date = item.get("txn_date") or item.get("date")
        if not merchant or amount is None or not raw_date:
            raise ValueError(
                f"Transaction {index + 1} needs merchant, amount, and date"
            )
        try:
            numeric_amount = float(amount)
            transaction_date = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Transaction {index + 1} has an invalid amount or ISO date"
            ) from error
        if not math.isfinite(numeric_amount) or numeric_amount <= 0:
            raise ValueError(
                f"Transaction {index + 1} amount must be greater than zero"
            )
        transactions.append(
            Transaction(
                merchant=str(merchant).strip(),
                amount=numeric_amount,
                txn_date=transaction_date,
            )
        )

    if not transactions:
        raise ValueError("Add at least one transaction")
    return transactions


def serialize_subscription(subscription) -> dict:
    return {
        "merchant": subscription.merchant,
        "typical_amount": subscription.typical_amount,
        "frequency": subscription.frequency,
        "annualized_cost": subscription.annualized_cost,
        "confidence": subscription.confidence,
        "occurrences": [
            {
                "merchant": transaction.merchant,
                "amount": round(transaction.amount, 2),
                "date": transaction.txn_date.isoformat(),
            }
            for transaction in subscription.occurrences
        ],
    }


def csv_to_transactions(contents: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(contents))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    rows = []
    for row in reader:
        rows.append(
            {
                "merchant": row.get("merchant") or row.get("merchant_name"),
                "amount": row.get("amount"),
                "date": row.get("date") or row.get("txn_date"),
            }
        )
    return rows


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SubscriptionDetector/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(
            status,
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return

        relative = "index.html" if path == "/" else path.removeprefix("/")
        requested = (STATIC / relative).resolve()
        if STATIC not in requested.parents or not requested.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        content_type = mimetypes.guess_type(requested.name)[0] or "text/plain"
        self._send(HTTPStatus.OK, requested.read_bytes(), content_type)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/detect":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2_000_000:
                raise ValueError("Request is too large")
            raw_body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            if "text/csv" in content_type:
                transactions_payload = csv_to_transactions(
                    raw_body.decode("utf-8-sig")
                )
                options = {}
            else:
                body = json.loads(raw_body.decode("utf-8"))
                if isinstance(body, list):
                    transactions_payload, options = body, {}
                else:
                    transactions_payload = body.get("transactions", [])
                    options = body
            transactions = parse_transactions(transactions_payload)
            subscriptions = detect_subscriptions(
                transactions,
                min_occurrences=int(options.get("min_occurrences", 3)),
                amount_tolerance=float(options.get("amount_tolerance", 0.10)),
            )
            self._json(
                HTTPStatus.OK,
                {
                    "transaction_count": len(transactions),
                    "subscription_count": len(subscriptions),
                    "subscriptions": [
                        serialize_subscription(subscription)
                        for subscription in subscriptions
                    ],
                },
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def log_message(self, format: str, *args) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def main() -> None:
    port = 5000
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Subscription detector running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()