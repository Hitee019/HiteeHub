"""
Subscription / recurring-charge detector.

Input: a list of transactions (as you'd get from Plaid's /transactions/get)
Output: a list of detected recurring subscriptions, each with:
    - merchant name
    - amount (typical/median charge)
    - frequency (weekly / monthly / annual)
    - annualized cost
    - confidence score
    - transaction history (for the user to verify)

Core idea:
1. Group transactions by normalized merchant name.
2. Within each merchant group, look for near-identical amounts recurring
   at roughly regular intervals.
3. Score confidence based on: amount consistency, interval consistency,
   and number of occurrences.
"""

from dataclasses import dataclass, field
from datetime import date
from statistics import mean, pstdev
from collections import defaultdict
import re


@dataclass
class Transaction:
    merchant: str
    amount: float          # positive = money out
    txn_date: date


@dataclass
class Subscription:
    merchant: str
    typical_amount: float
    frequency: str          # "weekly" | "monthly" | "quarterly" | "annual" | "irregular"
    annualized_cost: float
    confidence: float        # 0.0 - 1.0
    occurrences: list = field(default_factory=list)


# --- Step 1: normalize merchant names -----------------------------------
# Real-world bank feeds are messy: "NETFLIX.COM 8552654578 CA",
# "Netflix.com", "NETFLIX INTERNATION" all need to collapse to "Netflix".

def normalize_merchant(raw_name: str) -> str:
    name = raw_name.upper()
    name = re.sub(r'[^A-Z0-9 ]', ' ', name)          # strip punctuation
    name = re.sub(r'\b\d{4,}\b', '', name)            # strip long numeric IDs (phone #s, refs)
    name = re.sub(r'\s+', ' ', name).strip()
    # Take first 1-2 significant tokens — merchant names are usually front-loaded
    tokens = name.split(' ')
    significant = [t for t in tokens if t not in {
        'COM', 'INC', 'LLC', 'CA', 'US', 'THE', 'INTERNATIONAL', 'PAYMENT'
    }]
    return ' '.join(significant[:2]) if significant else name


# --- Step 2: group + detect intervals ------------------------------------

def days_between(d1: date, d2: date) -> int:
    return abs((d2 - d1).days)


FREQUENCY_BUCKETS = {
    'weekly':    (6, 8),
    'monthly':   (27, 33),
    'quarterly': (85, 95),
    'annual':    (355, 375),
}


def classify_interval(avg_days: float) -> str:
    for label, (lo, hi) in FREQUENCY_BUCKETS.items():
        if lo <= avg_days <= hi:
            return label
    return 'irregular'


def detect_subscriptions(transactions: list[Transaction],
                          min_occurrences: int = 3,
                          amount_tolerance: float = 0.10) -> list[Subscription]:
    """
    amount_tolerance: allowed relative variance in charge amount (10% default,
    since some subscriptions fluctuate slightly — usage-based tiers, taxes, FX).
    """
    groups = defaultdict(list)
    for txn in transactions:
        key = normalize_merchant(txn.merchant)
        groups[key].append(txn)

    results = []

    for merchant, txns in groups.items():
        if len(txns) < min_occurrences:
            continue

        txns_sorted = sorted(txns, key=lambda t: t.txn_date)
        amounts = [t.amount for t in txns_sorted]

        # Cluster by amount similarity first — a merchant might have both
        # a $9.99 and a $49.99 product; treat as separate subscriptions.
        amount_clusters = _cluster_by_amount(txns_sorted, amount_tolerance)

        for cluster in amount_clusters:
            if len(cluster) < min_occurrences:
                continue

            dates = [t.txn_date for t in cluster]
            intervals = [days_between(dates[i], dates[i + 1]) for i in range(len(dates) - 1)]

            avg_interval = mean(intervals)
            interval_std = pstdev(intervals) if len(intervals) > 1 else 0
            frequency = classify_interval(avg_interval)

            if frequency == 'irregular':
                continue  # not a subscription pattern

            typical_amount = mean([t.amount for t in cluster])
            amount_std = pstdev([t.amount for t in cluster]) if len(cluster) > 1 else 0

            # --- Confidence scoring ---
            # Lower std relative to mean = more confident it's a fixed recurring charge.
            interval_consistency = max(0, 1 - (interval_std / avg_interval))
            amount_consistency = max(0, 1 - (amount_std / typical_amount)) if typical_amount else 0
            occurrence_bonus = min(1.0, len(cluster) / 6)  # maxes out around 6+ occurrences

            confidence = round(
                0.4 * interval_consistency +
                0.4 * amount_consistency +
                0.2 * occurrence_bonus,
                2
            )

            annualized = _annualize(typical_amount, frequency)

            results.append(Subscription(
                merchant=merchant.title(),
                typical_amount=round(typical_amount, 2),
                frequency=frequency,
                annualized_cost=round(annualized, 2),
                confidence=confidence,
                occurrences=cluster,
            ))

    # Sort by annual cost descending — biggest leaks first (the emotional hook)
    return sorted(results, key=lambda s: s.annualized_cost, reverse=True)


def _cluster_by_amount(txns: list[Transaction], tolerance: float) -> list[list[Transaction]]:
    """Group same-merchant transactions into amount-similar clusters."""
    clusters = []
    for txn in txns:
        placed = False
        for cluster in clusters:
            cluster_avg = mean([t.amount for t in cluster])
            if abs(txn.amount - cluster_avg) / cluster_avg <= tolerance:
                cluster.append(txn)
                placed = True
                break
        if not placed:
            clusters.append([txn])
    return clusters


def _annualize(amount: float, frequency: str) -> float:
    multiplier = {
        'weekly': 52,
        'monthly': 12,
        'quarterly': 4,
        'annual': 1,
    }
    return amount * multiplier.get(frequency, 0)


# --- Example usage --------------------------------------------------------
if __name__ == '__main__':
    sample_txns = [
        Transaction('NETFLIX.COM 8552654578 CA', 15.49, date(2026, 1, 5)),
        Transaction('NETFLIX.COM 8552654578 CA', 15.49, date(2026, 2, 5)),
        Transaction('NETFLIX.COM 8552654578 CA', 15.49, date(2026, 3, 6)),
        Transaction('NETFLIX.COM 8552654578 CA', 15.49, date(2026, 4, 5)),
        Transaction('SPOTIFY USA', 11.99, date(2026, 1, 12)),
        Transaction('SPOTIFY USA', 11.99, date(2026, 2, 12)),
        Transaction('SPOTIFY USA', 11.99, date(2026, 3, 13)),
        Transaction('STARBUCKS #4521', 6.75, date(2026, 1, 3)),  # not recurring pattern
        Transaction('STARBUCKS #8832', 5.25, date(2026, 1, 20)),
        Transaction('PLANET FITNESS', 24.99, date(2026, 1, 1)),
        Transaction('PLANET FITNESS', 24.99, date(2026, 2, 1)),
        Transaction('PLANET FITNESS', 24.99, date(2026, 3, 1)),
        Transaction('PLANET FITNESS', 24.99, date(2026, 4, 1)),
        Transaction('PLANET FITNESS', 24.99, date(2026, 5, 1)),
    ]

    subs = detect_subscriptions(sample_txns)
    for s in subs:
        print(f"{s.merchant:20s} ${s.typical_amount:6.2f} / {s.frequency:9s} "
              f"-> ${s.annualized_cost:7.2f}/yr  (confidence: {s.confidence})")
