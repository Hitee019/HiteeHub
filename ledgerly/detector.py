"""Recurring subscription detection for transaction data."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean, pstdev
import re


@dataclass
class Transaction:
    merchant: str
    amount: float
    txn_date: date


@dataclass
class Subscription:
    merchant: str
    typical_amount: float
    frequency: str
    annualized_cost: float
    confidence: float
    occurrences: list[Transaction] = field(default_factory=list)


FREQUENCY_BUCKETS = {
    "weekly": (6, 8),
    "monthly": (27, 33),
    "quarterly": (85, 95),
    "annual": (355, 375),
}

_IGNORED_TOKENS = {
    "COM", "INC", "LLC", "CA", "US", "THE", "INTERNATIONAL", "PAYMENT",
}


def normalize_merchant(raw_name: str) -> str:
    name = raw_name.upper()
    name = re.sub(r"[^A-Z0-9 ]", " ", name)
    name = re.sub(r"\b\d{4,}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    tokens = [token for token in name.split(" ") if token not in _IGNORED_TOKENS]
    return " ".join(tokens[:2]) if tokens else name


def classify_interval(avg_days: float) -> str:
    for label, (low, high) in FREQUENCY_BUCKETS.items():
        if low <= avg_days <= high:
            return label
    return "irregular"


def detect_subscriptions(
    transactions: list[Transaction],
    min_occurrences: int = 3,
    amount_tolerance: float = 0.10,
) -> list[Subscription]:
    """Find stable, regularly timed charges grouped by normalized merchant."""
    if min_occurrences < 2:
        raise ValueError("min_occurrences must be at least 2")
    if not 0 <= amount_tolerance <= 1:
        raise ValueError("amount_tolerance must be between 0 and 1")

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        groups[normalize_merchant(transaction.merchant)].append(transaction)

    results: list[Subscription] = []
    for merchant, merchant_transactions in groups.items():
        if len(merchant_transactions) < min_occurrences:
            continue

        sorted_transactions = sorted(
            merchant_transactions, key=lambda transaction: transaction.txn_date
        )
        for cluster in _cluster_by_amount(sorted_transactions, amount_tolerance):
            if len(cluster) < min_occurrences:
                continue

            dates = [transaction.txn_date for transaction in cluster]
            intervals = [
                (dates[index + 1] - dates[index]).days
                for index in range(len(dates) - 1)
            ]
            average_interval = mean(intervals)
            frequency = classify_interval(average_interval)
            if frequency == "irregular":
                continue

            amounts = [transaction.amount for transaction in cluster]
            typical_amount = mean(amounts)
            interval_std = pstdev(intervals) if len(intervals) > 1 else 0
            amount_std = pstdev(amounts) if len(amounts) > 1 else 0
            interval_consistency = max(
                0, 1 - (interval_std / average_interval)
            )
            amount_consistency = max(
                0, 1 - (amount_std / typical_amount)
            ) if typical_amount else 0
            occurrence_bonus = min(1.0, len(cluster) / 6)
            confidence = round(
                0.4 * interval_consistency
                + 0.4 * amount_consistency
                + 0.2 * occurrence_bonus,
                2,
            )

            results.append(
                Subscription(
                    merchant=merchant.title(),
                    typical_amount=round(typical_amount, 2),
                    frequency=frequency,
                    annualized_cost=round(
                        _annualize(typical_amount, frequency), 2
                    ),
                    confidence=confidence,
                    occurrences=cluster,
                )
            )

    return sorted(results, key=lambda subscription: subscription.annualized_cost, reverse=True)


def _cluster_by_amount(
    transactions: list[Transaction], tolerance: float
) -> list[list[Transaction]]:
    clusters: list[list[Transaction]] = []
    for transaction in transactions:
        for cluster in clusters:
            average_amount = mean(item.amount for item in cluster)
            if average_amount and abs(transaction.amount - average_amount) / average_amount <= tolerance:
                cluster.append(transaction)
                break
        else:
            clusters.append([transaction])
    return clusters


def _annualize(amount: float, frequency: str) -> float:
    return amount * {
        "weekly": 52,
        "monthly": 12,
        "quarterly": 4,
        "annual": 1,
    }.get(frequency, 0)