"""簇级仓位权重蓝图：基于②聚类结果，对每簇 TOP1 基金做③仓位建议。

链路：预设镜像 → cluster.pipeline 聚类 → 取每簇 TOP1 基金净值 →
景气度(净值四因子) + 乖离度 → 目标权重(∑=100%) + 持仓推荐。
"""
from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app import db as database
from app import preset_access
from app.cluster.algo import pipeline as cluster_pipeline
from app.fund_holdings.crud import holdings_crud
from app.fund_nav.crud import nav_crud
from app.position.algo import pipeline as position_pipeline

bp = Blueprint("position", __name__, url_prefix="/api/position")

NAV_LOOKBACK = 260      # 取最近约 13 个月净值，够算 6m 动量 / MA60 / 一致性


@bp.post("/run")
@jwt_required()
def run():
    """对预设镜像聚类并算簇级仓位建议。body: ``{"preset_id": int}``。"""
    items, error = preset_access.resolve_items("items")
    if error:
        payload, status = error
        return jsonify(payload), status

    cluster_result = cluster_pipeline.run(items, preset_access.build_metrics(items))
    if cluster_result is None:
        return jsonify({"items": None, "reason": "有效基金不足（需 ≥3 只含股票持仓的基金）"})

    clusters = cluster_result["clusters"]
    top_codes = [c["funds"][0]["code"] for c in clusters if c.get("funds")]
    nav_by_code = {code: nav_crud.recent_series_dated(code, NAV_LOOKBACK) for code in top_codes}
    holdings_by_code = {code: holdings_crud.top_holdings(code, "stock") for code in top_codes}
    detail_by_code = {}
    for code in top_codes:
        detail = database.select_one("fund_details", {"fund_code": f"eq.{code}"})
        if detail:
            detail_by_code[code] = detail
    result = position_pipeline.run(clusters, nav_by_code, holdings_by_code, detail_by_code)
    result["cluster_meta"] = cluster_result["meta"]
    return jsonify(result)
