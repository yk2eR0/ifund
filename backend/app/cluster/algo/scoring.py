"""临时综合分（簇内排序用）。

①的完整评分缺年度排名数据，本轮用现有指标的近似分：
``0.40·z(sharpe_3y) + 0.30·z(risk_return_ratio_3y) + 0.15·z(log 规模) + 0.15·z(年限)``。
z 以中位数为中心、标准差缩放，clip 到 [-2,2]，缺失值取 0。
"""
from __future__ import annotations

import datetime
import math

import numpy as np  # pylint: disable=import-error

W_SHARPE = 0.40
W_RR = 0.30
W_SIZE = 0.15
W_AGE = 0.15


def _zscores(values: list[float | None]) -> list[float]:
    """中位数中心 + 标准差缩放的 z 值，缺失→0，clip[-2,2]。"""
    present = [v for v in values if v is not None]
    if not present:
        return [0.0] * len(values)
    center = float(np.median(present))
    std = float(np.std(present))
    if std == 0:
        return [0.0] * len(values)
    return [float(np.clip((v - center) / std, -2.0, 2.0)) if v is not None else 0.0
            for v in values]


def _age_years(establish_date: str | None) -> float | None:
    """成立日期字符串（YYYY-MM-DD）→ 距今年限；无法解析返回 None。"""
    if not establish_date:
        return None
    try:
        start = datetime.date.fromisoformat(str(establish_date)[:10])
    except ValueError:
        return None
    return (datetime.date.today() - start).days / 365.25


def composite_scores(codes: list[str], metrics: dict[str, dict]) -> dict[str, float]:
    """返回 ``code → 综合分``。metrics[code] 需含 sharpe_3y/risk_return_ratio_3y/scale/establish_date。"""
    def col(key):
        return [metrics.get(c, {}).get(key) for c in codes]

    z_sharpe = _zscores(col("sharpe_3y"))
    z_rr = _zscores(col("risk_return_ratio_3y"))
    sizes = [s if (s := metrics.get(c, {}).get("scale")) and s > 0 else None for c in codes]
    z_size = _zscores([math.log(s) if s else None for s in sizes])
    z_age = _zscores([_age_years(metrics.get(c, {}).get("establish_date")) for c in codes])

    scores = {}
    for i, code in enumerate(codes):
        scores[code] = round(
            W_SHARPE * z_sharpe[i] + W_RR * z_rr[i]
            + W_SIZE * z_size[i] + W_AGE * z_age[i], 4)
    return scores
