"""SuperMemo-2 (SM-2) spaced repetition scheduling.

Applies the SM-2 algorithm on a 1-4 rating scale (Again / Hard / Good / Easy):

- rating 1 (Again): recall failed -> interval resets to 1 day, repetitions = 0,
  ease factor (EF) decreases.
- rating 2 (Hard): recall succeeded with difficulty -> short interval bump.
- rating 3 (Good): recall succeeded -> interval grows by current EF.
- rating 4 (Easy): recall succeeded easily -> interval grows faster.

EF is updated using the classic SM-2 quality formula and floored at 1.3.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class SM2Result:
    ease_factor: float
    interval_days: int
    repetitions: int
    next_review_at: datetime


def _new_ease_factor(ease_factor: float, rating: int) -> float:
    """SM-2 EF update from a 1-4 rating mapped onto the 0-5 quality axis."""
    quality = {1: 2, 2: 3, 3: 4, 4: 5}[rating]
    updated = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return max(updated, 1.3)


def sm2_review(
    ease_factor: float = 2.5,
    interval_days: int = 0,
    repetitions: int = 0,
    rating: int = 3,
    now: Optional[datetime] = None,
) -> SM2Result:
    """Compute the next scheduling state given the current state and a rating.

    Args:
        ease_factor: current ease factor (default 2.5).
        interval_days: current review interval in days (0 for new cards).
        repetitions: number of successful recalls in a row.
        rating: SM-2 quality on a 1-4 scale.
        now: reference clock for computing the due date.
    """
    rating = int(rating)
    now = now or datetime.utcnow()
    ef = _new_ease_factor(ease_factor, rating)

    if rating < 3:
        # Failed recall: the card is relearned from scratch.
        repetitions = 0
        interval_days = 1
    elif repetitions == 0:
        # First successful recall.
        repetitions = 1
        interval_days = 1
    elif repetitions == 1:
        # Second successful recall.
        repetitions = 2
        interval_days = 6
    else:
        repetitions += 1
        interval_days = max(1, round(interval_days * ef))

    return SM2Result(
        ease_factor=round(ef, 2),
        interval_days=interval_days,
        repetitions=repetitions,
        next_review_at=now + timedelta(days=interval_days),
    )
