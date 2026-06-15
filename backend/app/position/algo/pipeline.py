"""仓位编排：②聚类的簇列表 + 各簇 TOP1 净值 → 景气度/乖离/目标权重/推荐 + 组合净值走势。"""
from __future__ import annotations

from datetime import date

from app.position.algo import deviation, prosperity, recommend, weights

MIN_NAV_POINTS = 60      # 低于此点数视为净值不足（景气度会退化为中性）
RISK_FREE_ANNUAL = 0.0   # 夏普比率的无风险利率（简化为 0，即「收益/波动」口径）


def _portfolio_curve(dated_list: list[list[tuple[str, float]]],
                     weights_list: list[float]) -> tuple[list[dict], float]:
    """按权重合成组合净值与回撤曲线。

    各代表基金净值绝对值不同，不能直接加权；先在共同起点 rebase 到 1.0，
    再按归一化权重加权，组合净值从 1.0 起步。回撤 = 当前相对历史峰值的跌幅。

    Args:
        dated_list: 每只代表基金的 ``(trade_date, 累计净值)`` 升序列表
        weights_list: 对应目标权重（∑≈1）

    Returns:
        (``[{"date","nav","drawdown"}]``, 最大回撤)；drawdown 为负百分比（underwater）。
    """
    # 仅保留有净值且权重为正的基金，转成 date→nav 便于按日对齐
    funds = [(dict(dated), w)
             for dated, w in zip(dated_list, weights_list) if dated and w > 0]
    if not funds:
        return [], 0.0

    # 取所有基金共有的交易日（交集），确保每天都能完整加权
    common = set(funds[0][0])
    for nav_map, _ in funds[1:]:
        common &= nav_map.keys()
    dates = sorted(common)
    if len(dates) < 2:
        return [], 0.0

    total_w = sum(w for _, w in funds)
    bases = [nav_map[dates[0]] for nav_map, _ in funds]  # 各基金共同起点净值

    curve: list[dict] = []
    peak = max_dd = 0.0
    for day in dates:
        nav = sum((nav_map[day] / base) * (w / total_w)
                  for (nav_map, w), base in zip(funds, bases))
        peak = max(peak, nav)
        dd = (nav - peak) / peak if peak > 0 else 0.0   # ≤0
        max_dd = min(max_dd, dd)
        curve.append({"date": day, "nav": round(nav, 4), "drawdown": round(dd * 100, 2)})
    return curve, round(-max_dd, 4)


def _portfolio_stats(curve: list[dict]) -> dict:
    """从组合净值曲线算年化收益/年化波动/夏普比率。

    用逐点简单收益率，按实际日期跨度推断「每年观测数」做年化（兼容日频/周频）。
    夏普 = 年化超额收益 / 年化波动，无风险利率见 ``RISK_FREE_ANNUAL``。
    """
    if len(curve) < 2:
        return {"annual_return": 0.0, "annual_vol": 0.0, "sharpe": 0.0}

    navs = [p["nav"] for p in curve]
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1) if len(rets) > 1 else 0.0
    std = var ** 0.5

    span_days = (date.fromisoformat(curve[-1]["date"]) - date.fromisoformat(curve[0]["date"])).days or 1
    periods_per_year = len(rets) * 365.25 / span_days
    annual_return = (navs[-1] / navs[0]) ** (365.25 / span_days) - 1
    annual_vol = std * periods_per_year ** 0.5
    sharpe = (annual_return - RISK_FREE_ANNUAL) / annual_vol if annual_vol > 0 else 0.0
    return {"annual_return": round(annual_return, 4),
            "annual_vol": round(annual_vol, 4),
            "sharpe": round(sharpe, 2)}


def run(clusters: list[dict], nav_by_code: dict[str, list[tuple[str, float]]]) -> dict:
    """clusters：cluster pipeline 的簇列表；nav_by_code：code→``(trade_date, 累计净值)`` 升序。

    每簇取综合分第一的基金（``funds[0]``）作为代表，算景气度+乖离+目标权重+推荐。
    返回 ``{"items": [...], "meta": {...}}``，items 按目标权重降序。
    """
    valid = [c for c in clusters if c.get("funds")]
    dated_list = [nav_by_code.get(c["funds"][0]["code"], []) for c in valid]
    series_list = [[nav for _, nav in dated] for dated in dated_list]

    pros = prosperity.compute(series_list)
    devs = [deviation.deviation(s) for s in series_list]
    target = weights.target_weights([p["total"] for p in pros], devs)
    base = round(1.0 / len(valid), 4) if valid else 0.0

    items, missing = [], []
    for i, cluster in enumerate(valid):
        fund = cluster["funds"][0]
        points = len(series_list[i])
        if points < MIN_NAV_POINTS:
            missing.append(fund["code"])
        items.append({
            "cluster_id": cluster["cluster_id"],
            "cluster_name": cluster["name"],
            "top_industries": cluster.get("top_industries", []),
            "fund_count": cluster.get("fund_count", 0),
            "fund": {
                "code": fund["code"], "name": fund["name"], "score": fund["score"],
                "sharpe_3y": fund["sharpe_3y"], "scale": fund["scale"],
            },
            "nav_points": points,
            "prosperity": pros[i],
            "deviation": devs[i],
            "base_weight": base,
            "weight": target[i],
            "recommendation": recommend.recommend(
                pros[i]["total"], devs[i]["combined"], target[i], base),
        })
    items.sort(key=lambda x: x["weight"], reverse=True)

    # 按目标权重合成组合净值与回撤走势（rebase 到 1.0 后加权），并算年化/夏普
    curve, max_drawdown = _portfolio_curve(dated_list, target)
    stats = _portfolio_stats(curve)

    return {"items": items,
            "portfolio": {"curve": curve, "max_drawdown": max_drawdown, **stats},
            "meta": {"n_clusters": len(valid), "base_weight": base, "nav_missing": missing}}
