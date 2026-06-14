"""把聚类结果组装成可视化用的簇结构：簇名、特征股、行业占比、簇内基金。

- 簇名 = 簇内行业均值 top3 标签。
- 特征股 = 簇内股票均值减全池基线后差值最大的股票（凸显「这簇独有的偏好」）。
- 簇内基金按临时综合分降序。
"""
from __future__ import annotations

import numpy as np  # pylint: disable=import-error

from app.cluster.algo.matrix import FundMatrix

TOP_INDUSTRIES = 3
SIGNATURE_STOCKS = 5
SECONDARY_STOCKS = 12
CAPITAL_STOCKS = 12      # 实际资金暴露榜展示的股票数
MIN_OVERLAP = 2          # 次要股票至少被簇内 2 只基金共同持有才算「重叠」


def _top_industries(mat: FundMatrix, rows: list[int]) -> list[dict]:
    mean = mat.ind_matrix[rows].mean(axis=0)
    order = np.argsort(mean)[::-1]
    out = []
    for col in order[:TOP_INDUSTRIES]:
        if mean[col] <= 0:
            break
        out.append({"label": mat.ind_cols[col], "ratio": round(float(mean[col]), 2)})
    return out


def _stock_entry(mat: FundMatrix, col: int, overlap: int, edge: float | None = None) -> dict:
    code = mat.stock_cols[col]
    entry = {"code": code, "name": mat.stock_names.get(code, code),
             "industry": mat.stock_industry.get(code, "其他"), "overlap": overlap}
    if edge is not None:
        entry["edge"] = round(edge, 2)
    return entry


def _signature_stocks(mat: FundMatrix, rows: list[int], baseline: np.ndarray,
                      counts: np.ndarray) -> list[dict]:
    """主要特征股：簇内均值高出全池基线最多的股票（含簇内重叠基金数）。"""
    diff = mat.stk_matrix[rows].mean(axis=0) - baseline
    order = np.argsort(diff)[::-1]
    out = []
    for col in order[:SIGNATURE_STOCKS]:
        if diff[col] <= 0:
            break
        out.append(_stock_entry(mat, col, int(counts[col]), float(diff[col])))
    return out


def _secondary_stocks(mat: FundMatrix, counts: np.ndarray, exclude: set[str]) -> list[dict]:
    """次要重叠股：簇内被多只基金共同持有、但未入主要列表的股票（按重叠数降序）。"""
    out = []
    for col in np.argsort(counts)[::-1]:
        if counts[col] < MIN_OVERLAP:
            break
        if mat.stock_cols[col] in exclude:
            continue
        out.append(_stock_entry(mat, col, int(counts[col])))
        if len(out) >= SECONDARY_STOCKS:
            break
    return out


def _capital_exposure(mat: FundMatrix, rows: list[int]) -> dict:
    """实际资金暴露（规模加权）：按股票聚合簇内各基金的持仓市值（万元）。

    口径为 top10 重仓市值之和（快照只存重仓），单位换算成亿元；含每只占簇内
    总重仓市值的比例（``mv_pct``）与持有该股的基金数（``overlap``）。
    """
    agg: dict[str, dict] = {}
    for row in rows:
        for h in mat.holdings.get(mat.codes[row], []):
            slot = agg.setdefault(h["code"], {
                "code": h["code"], "name": h["name"], "industry": h["industry"],
                "mv": 0.0, "overlap": 0})
            slot["mv"] += h.get("mv") or 0.0
            slot["overlap"] += 1
    total = sum(s["mv"] for s in agg.values())
    ranked = sorted(agg.values(), key=lambda s: s["mv"], reverse=True)[:CAPITAL_STOCKS]
    stocks = [{
        "code": s["code"], "name": s["name"], "industry": s["industry"],
        "overlap": s["overlap"],
        "mv_yi": round(s["mv"] / 10000.0, 2),
        "mv_pct": round(s["mv"] / total * 100, 1) if total else 0.0,
    } for s in ranked]
    return {"total_yi": round(total / 10000.0, 2), "stocks": stocks}


def other_cluster(codes: list[str], scores: dict[str, float],
                  metrics: dict[str, dict]) -> dict:
    """无股票持仓、未能参与聚类的基金归一个「其他」簇（cluster_id=0），不丢弃。"""
    funds = []
    for code in codes:
        meta = metrics.get(code, {})
        funds.append({
            "code": code, "name": meta.get("name", ""),
            "score": scores.get(code, 0.0),
            "sharpe_3y": meta.get("sharpe_3y"),
            "scale": meta.get("scale"),
            "holdings": [],
        })
    funds.sort(key=lambda f: f["score"], reverse=True)
    return {
        "cluster_id": 0,
        "name": "其他（无股票持仓，未参与聚类）",
        "top_industries": [],
        "signature_stocks": [],
        "secondary_stocks": [],
        "capital_exposure": {"total_yi": 0.0, "stocks": []},
        "fund_count": len(funds),
        "funds": funds,
    }


def assemble(mat: FundMatrix, labels: list[int], scores: dict[str, float],
             metrics: dict[str, dict]) -> list[dict]:
    """返回按基金数降序排列的簇列表。"""
    baseline = mat.stk_matrix.mean(axis=0)
    clusters: dict[int, list[int]] = {}
    for row, lab in enumerate(labels):
        clusters.setdefault(lab, []).append(row)

    result = []
    for lab, rows in clusters.items():
        top_inds = _top_industries(mat, rows)
        funds = []
        for row in rows:
            code = mat.codes[row]
            meta = metrics.get(code, {})
            funds.append({
                "code": code, "name": meta.get("name", ""),
                "score": scores.get(code, 0.0),
                "sharpe_3y": meta.get("sharpe_3y"),
                "scale": meta.get("scale"),
                "holdings": mat.holdings.get(code, []),
            })
        funds.sort(key=lambda f: f["score"], reverse=True)
        counts = (mat.stk_matrix[rows] > 0).sum(axis=0)
        signature = _signature_stocks(mat, rows, baseline, counts)
        secondary = _secondary_stocks(mat, counts, {s["code"] for s in signature})
        result.append({
            "cluster_id": lab,
            "name": " / ".join(i["label"] for i in top_inds) or "未分类",
            "top_industries": top_inds,
            "signature_stocks": signature,
            "secondary_stocks": secondary,
            "capital_exposure": _capital_exposure(mat, rows),
            "fund_count": len(rows),
            "funds": funds,
        })
    result.sort(key=lambda c: c["fund_count"], reverse=True)
    return result
