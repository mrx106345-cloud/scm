"""Demand classification (Part E1). ADI/CV2 on non-zero weeks only.

ADI = n_weeks / n_nonzero. CV2 = (std/mean)^2 of nonzero sizes (population std).
smooth (ADI<1.32, CV2<0.49), erratic (ADI<1.32, CV2>=0.49),
intermittent (ADI>=1.32, CV2<0.49), lumpy (both high).
<8 weeks history -> new (moving average, low confidence).
"""

from __future__ import annotations

import statistics


def classify_series(weekly_qty: list[float]) -> dict[str, object]:
    """Classify a weekly demand series. Returns class + ADI + CV2 + confidence."""
    n = len(weekly_qty)
    if n < 8:
        return {"class": "new", "adi": None, "cv2": None, "confidence": "low"}
    nonzero = [q for q in weekly_qty if q != 0]
    if not nonzero:
        return {"class": "new", "adi": None, "cv2": None, "confidence": "low"}
    adi = n / len(nonzero)
    mean = statistics.fmean(nonzero)
    if mean == 0:
        return {"class": "new", "adi": adi, "cv2": None, "confidence": "low"}
    sd = statistics.pstdev(nonzero)
    cv2 = (sd / mean) ** 2
    if adi < 1.32 and cv2 < 0.49:
        cls = "smooth"
    elif adi < 1.32:
        cls = "erratic"
    elif cv2 < 0.49:
        cls = "intermittent"
    else:
        cls = "lumpy"
    return {"class": cls, "adi": adi, "cv2": cv2, "confidence": "high"}
