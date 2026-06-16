"""实盘对账核心：把③簇级目标权重落到用户真实持仓上，按赛道算每笔加/减/建/清的金额。

设计取向（契合「不折腾」哲学）：
- **按赛道（簇）对齐**，不按基金代码精确匹配——只看每个赛道总仓位够不够，不强制把手里的
  基金换成系统选的代表基金（低换手、连贯）。
- **金额化**：目标按「总资产 = 持仓市值 + 可投现金」分配，逐赛道算差额。
- **缓冲带抗噪**：偏离在 ``band×总资产`` 或 ``MIN_TRADE`` 以内就「保持不动」。
- **现金配平不借钱**：买入需求超过「可投现金 + 卖出释放」时，所有买入等比缩减，缩到不足
  起投门槛的降级为「暂缓」。一轮可能未完全到位，summary 标注受资金约束。

赛道外持仓（归类失败）一律建议清仓释放现金；目标权重不含赛道外，故清仓后现金被买入吸收。
"""
from __future__ import annotations

from app.reconcile.algo import classify

DEFAULT_BAND = 0.03      # 缓冲带：总资产的 3 个百分点（绝对），对「按金额」最直观
MIN_TRADE_YUAN = 100.0   # 小于此金额的动作忽略（抗噪 + 申赎门槛）


def reconcile(target_items: list[dict], holdings: list[dict], cash: float,
              band: float, clusters: list[dict], ind_idx: dict) -> dict:
    """对账。

    Args:
        target_items: ③仓位建议的 items（含 ``cluster_id/cluster_name/weight/fund``）。
        holdings: 用户持仓行 ``[{fund_code, fund_name, market_value}]``。
        cash: 可投现金（元）。
        band: 缓冲带（占总资产比例）。
        clusters: 聚类簇列表（含全部成员，供赛道归类）。
        ind_idx: 股票→行业映射（``industry_crud.industry_index()``）。

    Returns:
        ``{"rows", "summary", "meta"}``。
    """
    code2cluster = classify.build_code_to_cluster(clusters)
    name2cluster = classify.build_name_index(clusters)
    cluster_vecs = classify.cluster_vectors(clusters)

    cash = max(0.0, float(cash or 0.0))
    held_total = sum(float(h.get("market_value") or 0.0) for h in holdings)
    total_asset = held_total + cash

    # 1. 归类：每只持仓 → 赛道（A/C 同基金落同一赛道、市值相加），失败入 outside
    per_cluster_actual: dict[int, float] = {}
    cluster_user_funds: dict[int, list[dict]] = {}
    outside: list[dict] = []
    match_counts = {"exact": 0, "name": 0, "similar": 0, "outside": 0, "no_data": 0}
    for h in holdings:
        code = str(h.get("fund_code") or "").strip()
        mv = float(h.get("market_value") or 0.0)
        name = h.get("fund_name") or ""
        cid, match, sim = classify.classify_fund(
            code, name, code2cluster, name2cluster, cluster_vecs, ind_idx)
        match_counts[match] = match_counts.get(match, 0) + 1
        entry = {"code": code, "name": name, "market_value": round(mv, 2),
                 "match": match, "sim": sim}
        if cid is None:
            outside.append(entry)
        else:
            per_cluster_actual[cid] = per_cluster_actual.get(cid, 0.0) + mv
            cluster_user_funds.setdefault(cid, []).append(entry)

    band_yuan = band * total_asset
    rows: list[dict] = []
    buys: list[tuple[int, float]] = []   # (rows 下标, 期望买入金额)，供现金不足时等比缩减
    sell_total = 0.0

    # 2~3. 逐目标赛道：目标金额 = weight×总资产，与实际差额按缓冲带判加/减/建/不动
    for it in target_items:
        cid = it["cluster_id"]
        weight = float(it.get("weight") or 0.0)
        target = weight * total_asset
        actual = per_cluster_actual.get(cid, 0.0)
        diff = target - actual
        user_funds = sorted(cluster_user_funds.get(cid, []),
                            key=lambda x: x["market_value"], reverse=True)
        rep = it.get("fund") or {}

        if user_funds:
            biggest = user_funds[0]
            act_fund = {"code": biggest["code"], "name": biggest["name"]}
            match, sim = biggest["match"], biggest["sim"]
        else:
            act_fund = {"code": rep.get("code", ""), "name": rep.get("name", "")}
            match, sim = None, None

        row = {
            "cluster_id": cid, "cluster_name": it.get("cluster_name", ""),
            "weight": round(weight, 4), "target": round(target, 2),
            "actual": round(actual, 2), "target_fund": act_fund,
            "user_funds": user_funds, "match": match, "sim": sim,
        }

        if abs(diff) <= band_yuan or abs(diff) < MIN_TRADE_YUAN:
            row["action"] = "hold"
            row["amount"] = 0.0
            row["note"] = "已在目标 ± 缓冲带内，保持不动（抗噪）"
        elif diff > 0:
            row["amount"] = round(diff, 2)
            if actual < MIN_TRADE_YUAN:   # 空仓 → 建仓买代表基金
                row["action"] = "open"
                row["target_fund"] = {"code": rep.get("code", ""), "name": rep.get("name", "")}
                row["note"] = f"该赛道当前空仓，建议买入代表基金「{rep.get('name', '')}」建仓"
            else:
                row["action"] = "add"
                row["note"] = f"低配，建议加仓「{act_fund['name']}」"
            buys.append((len(rows), diff))
        else:   # diff < 0 → 减仓
            row["action"] = "trim"
            row["amount"] = round(diff, 2)   # 负数
            row["note"] = f"超配，建议减仓「{act_fund['name']}」"
            sell_total += -diff
        rows.append(row)

    # 4. 赛道外 → 清仓释放现金
    outside_value = 0.0
    for o in outside:
        outside_value += o["market_value"]
        sell_total += o["market_value"]
        note = ("库中无该基金持仓数据，无法归类（非真赛道外，建议先采集其持仓再对账）"
                if o["match"] == "no_data"
                else f"不属于当前组合任何赛道（最高相似度 {o['sim']}），建议清仓释放现金")
        rows.append({
            "cluster_id": None, "cluster_name": "赛道外",
            "weight": 0.0, "target": 0.0, "actual": o["market_value"],
            "target_fund": {"code": o["code"], "name": o["name"]},
            "user_funds": [o], "match": o["match"], "sim": o["sim"],
            "action": "exit", "amount": round(-o["market_value"], 2), "note": note,
        })

    # 5. 现金配平：买入需求 > 可投（现金 + 卖出释放）时，所有买入等比缩减（不借钱）
    available = cash + sell_total
    want_buy = sum(amt for _, amt in buys)
    scaled = False
    buy_total = 0.0
    if want_buy > available + 1e-6 and want_buy > 0:
        scaled = True
        scale = available / want_buy
        for idx, amt in buys:
            new_amt = round(amt * scale, 2)
            if new_amt < MIN_TRADE_YUAN:   # 缩到不足起投 → 暂缓
                rows[idx]["action"] = "hold"
                rows[idx]["amount"] = 0.0
                rows[idx]["note"] += "（本轮资金不足，暂缓建/加仓）"
            else:
                rows[idx]["amount"] = new_amt
                buy_total += new_amt
    else:
        for idx, amt in buys:
            rows[idx]["amount"] = round(amt, 2)
            buy_total += rows[idx]["amount"]

    leftover_cash = round(available - buy_total, 2)

    counts = {"open": 0, "add": 0, "trim": 0, "hold": 0, "exit": 0}
    for r in rows:
        counts[r["action"]] = counts.get(r["action"], 0) + 1

    summary = {
        "total_asset": round(total_asset, 2),
        "held_total": round(held_total, 2),
        "cash": round(cash, 2),
        "outside_value": round(outside_value, 2),
        "buy_total": round(buy_total, 2),
        "sell_total": round(sell_total, 2),
        "leftover_cash": leftover_cash,
        "band": band, "scaled": scaled,
        "counts": counts,
    }
    meta = {
        "n_target_clusters": len(target_items),
        "match_counts": match_counts,
        "outside_count": len(outside),
    }
    return {"rows": rows, "summary": summary, "meta": meta}
