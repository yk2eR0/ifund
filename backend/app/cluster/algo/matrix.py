"""从镜像快照构建基金画像矩阵：fund×stock 与 fund×industry。

输入是快照 ``items``（每项内嵌 top10 持仓）。只保留含股票持仓的基金，其余剔除并计入
``dropped``。``stock_cols`` / ``ind_cols`` 是矩阵的列名（股票代码 / 行业标签），用于后续
特征股、簇标签的回译。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np  # pylint: disable=import-error

from app.stock_industry.crud import industry_crud


@dataclass
class FundMatrix:
    """基金画像矩阵集合。"""

    codes: list[str]                 # 基金代码（行顺序）
    stock_cols: list[str]            # 股票代码（stk_matrix 列顺序）
    stock_names: dict[str, str]      # 股票代码 → 简称
    stock_industry: dict[str, str]   # 股票代码 → 申万三级（聚类标签）
    ind_cols: list[str]              # 行业标签（ind_matrix 列顺序）
    stk_matrix: np.ndarray           # fund × stock，值=持仓占比
    ind_matrix: np.ndarray           # fund × industry，值=按行业累加的持仓占比
    holdings: dict[str, list[dict]]  # 基金代码 → 持仓明细 [{code,name,ratio,industry}]


def _stock_holdings(item: dict) -> list[dict]:
    """取一只基金的股票持仓（过滤非股票、无代码、无占比）。"""
    out = []
    for h in item.get("holdings") or []:
        if h.get("holding_type") != "stock":
            continue
        code = h.get("asset_code")
        ratio = h.get("hold_ratio")
        if code and ratio:
            out.append(h)
    return out


def build(items: list[dict]) -> tuple[FundMatrix, list[str]]:
    """构建矩阵；返回 ``(FundMatrix, dropped_codes)``，dropped=无股票持仓未参与聚类的基金代码。"""
    idx = industry_crud.industry_index()
    paired = [(it, _stock_holdings(it)) for it in items]
    valid = [(it, hs) for it, hs in paired if hs]
    dropped_codes = [it["code"] for it, hs in paired if not hs and it.get("code")]

    codes = [it["code"] for it, _ in valid]
    stock_set: dict[str, str] = {}
    stock_ind: dict[str, str] = {}
    ind_set: list[str] = []
    holdings: dict[str, list[dict]] = {}
    for it, holds in valid:
        detail = []
        for h in holds:
            code = h["asset_code"]
            label = industry_crud.label_of(code, idx)
            stock_set.setdefault(code, h.get("asset_name") or "")
            stock_ind.setdefault(code, label)
            if label not in ind_set:
                ind_set.append(label)
            detail.append({"code": code, "name": h.get("asset_name") or "",
                           "ratio": float(h["hold_ratio"]), "industry": label,
                           "mv": float(h.get("hold_market_value") or 0.0)})
        detail.sort(key=lambda d: d["ratio"], reverse=True)
        holdings[it["code"]] = detail

    stock_cols = list(stock_set.keys())
    stk_pos = {c: i for i, c in enumerate(stock_cols)}
    ind_pos = {c: i for i, c in enumerate(ind_set)}

    stk = np.zeros((len(codes), len(stock_cols)), dtype=float)
    ind = np.zeros((len(codes), len(ind_set)), dtype=float)
    for row, (_, holds) in enumerate(valid):
        for h in holds:
            ratio = float(h["hold_ratio"])
            stk[row, stk_pos[h["asset_code"]]] += ratio
            ind[row, ind_pos[stock_ind[h["asset_code"]]]] += ratio

    return FundMatrix(
        codes=codes, stock_cols=stock_cols, stock_names=stock_set,
        stock_industry=stock_ind, ind_cols=ind_set, stk_matrix=stk, ind_matrix=ind,
        holdings=holdings,
    ), dropped_codes
