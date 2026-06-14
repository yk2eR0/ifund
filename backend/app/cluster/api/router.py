"""基金行业暴露聚类蓝图：对某预设的镜像快照做②聚类分析。"""
from __future__ import annotations

import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db as database
from app.cluster.algo import pipeline

bp = Blueprint("cluster", __name__, url_prefix="/api/cluster")


def _current_user_id() -> int:
    user = database.select_one("users", {"username": f"eq.{get_jwt_identity()}"})
    return user["id"] if user else 0


def _owned_preset(preset_id: int, user_id: int):
    return database.select_one("query_presets", {
        "id": f"eq.{preset_id}", "user_id": f"eq.{user_id}",
    })


def _metrics(items: list[dict]) -> dict[str, dict]:
    """每只基金的展示/评分指标：快照内字段 + fund_details 补 risk_return/成立日期。"""
    metrics: dict[str, dict] = {}
    for it in items:
        code = it.get("code")
        if code:
            metrics[code] = {
                "name": it.get("name", ""),
                "sharpe_3y": it.get("sharpe_3y"),
                "scale": it.get("scale"),
            }
    for code, metric in metrics.items():
        detail = database.select_one("fund_details", {"fund_code": f"eq.{code}"})
        if detail:
            metric["risk_return_ratio_3y"] = detail.get("risk_return_ratio_3y")
            metric["establish_date"] = detail.get("establish_date")
    return metrics


@bp.post("/run")
@jwt_required()
def run():
    """对预设的镜像快照聚类。body: ``{"preset_id": int}``。"""
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    preset_id = data.get("preset_id")
    if not preset_id:
        return jsonify({"detail": "preset_id required"}), 400
    if not _owned_preset(preset_id, user_id):
        return jsonify({"detail": "preset not found"}), 404

    snapshot = database.select_one("fund_snapshots", {
        "user_id": f"eq.{user_id}", "preset_id": f"eq.{preset_id}",
    })
    if not snapshot:
        return jsonify({"clusters": None, "reason": "该预设尚无镜像快照，请先在筛选页保存镜像"})

    items = json.loads(snapshot.get("items_json") or "[]")
    result = pipeline.run(items, _metrics(items))
    if result is None:
        return jsonify({"clusters": None, "reason": "有效基金不足（需 ≥3 只含股票持仓的基金）"})
    return jsonify(result)
