"""实盘对账蓝图：实盘 CRUD + 持仓 CRUD + 对账计算。全部按 user_id 隔离。

一个用户可有多个实盘（自己的 + 代管他人的），每个实盘关联一套仓位建议（预设）。
链路：选实盘 → 实盘的持仓 + 关联预设 → 复用 ③仓位的目标权重与聚类簇 →
``reconcile`` 按赛道对齐算每笔加/减/建/清金额。持仓持久化；现金/缓冲带/cap 走请求体不落库。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import preset_access
from app.position.api.router import compute_position
from app.position.algo import optimize
from app.reconcile.algo import reconcile as recon_algo
from app.reconcile.crud import holdings_store, portfolios_store
from app.stock_industry.crud import industry_crud

bp = Blueprint("reconcile", __name__, url_prefix="/api/reconcile")

CAP_MIN, CAP_MAX = 0.10, 0.30
BAND_MIN, BAND_MAX = 0.005, 0.10


def _clamp(val, lo, hi, default):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return default
    return min(hi, max(lo, v))


def _resolve_portfolio(uid: int):
    """从 query/body 取 portfolio_id 并校验归属；缺省则用默认实盘。

    返回 ``(portfolio, error)``：error 为 ``(payload, status)`` 或 None。
    """
    pid = request.args.get("portfolio_id")
    if pid is None:
        body = request.get_json(silent=True) or {}
        pid = body.get("portfolio_id")
    if pid is None:
        return portfolios_store.ensure_default(uid), None
    pf = portfolios_store.get_portfolio(int(pid), uid)
    if not pf:
        return None, ({"detail": "portfolio not found"}, 404)
    return pf, None


# ── 实盘账户 CRUD ──────────────────────────────────────────────

@bp.get("/portfolios")
@jwt_required()
def list_portfolios():
    """列出当前用户的全部实盘（保证至少有一个默认实盘）。"""
    uid = preset_access.current_user_id()
    portfolios_store.ensure_default(uid)
    return jsonify({"items": portfolios_store.list_portfolios(uid)})


@bp.post("/portfolios")
@jwt_required()
def create_portfolio():
    """新建实盘。body: ``{name, preset_id?}``。"""
    uid = preset_access.current_user_id()
    body = request.get_json(silent=True) or {}
    pf = portfolios_store.create_portfolio(uid, body.get("name", ""), body.get("preset_id"))
    return jsonify(pf)


@bp.patch("/portfolios/<int:pid>")
@jwt_required()
def update_portfolio(pid: int):
    """改名 / 关联预设。body: ``{name?, preset_id?}``（含 preset_id 键即更新，可置空取消关联）。"""
    uid = preset_access.current_user_id()
    body = request.get_json(silent=True) or {}
    set_preset = "preset_id" in body
    pf = portfolios_store.update_portfolio(
        pid, uid, name=body.get("name"),
        preset_id=body.get("preset_id"), set_preset=set_preset,
    )
    if not pf:
        return jsonify({"detail": "portfolio not found"}), 404
    return jsonify(pf)


@bp.delete("/portfolios/<int:pid>")
@jwt_required()
def delete_portfolio(pid: int):
    """删除实盘及其持仓。"""
    uid = preset_access.current_user_id()
    if not portfolios_store.delete_portfolio(pid, uid):
        return jsonify({"detail": "portfolio not found"}), 404
    return jsonify({"ok": True})


# ── 持仓 CRUD（按 portfolio_id 隔离）──────────────────────────

@bp.get("/holdings")
@jwt_required()
def get_holdings():
    """列出某实盘的持仓。query: ``?portfolio_id=``（缺省用默认实盘）。"""
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status
    return jsonify({"portfolio_id": pf["id"], "items": holdings_store.list_holdings(pf["id"])})


@bp.post("/holdings")
@jwt_required()
def upsert_holding():
    """新增/更新一只持仓。body: ``{portfolio_id?, fund_code, fund_name?, market_value, cost?}``。"""
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status
    body = request.get_json(silent=True) or {}
    code = str(body.get("fund_code") or "").strip()
    if not code:
        return jsonify({"detail": "fund_code required"}), 400
    try:
        mv = float(body.get("market_value") or 0)
    except (TypeError, ValueError):
        return jsonify({"detail": "market_value invalid"}), 400
    cost = body.get("cost")
    try:
        cost = float(cost) if cost is not None and cost != "" else None
    except (TypeError, ValueError):
        cost = None
    row = holdings_store.upsert_holding(pf["id"], uid, code, body.get("fund_name", ""), mv, cost)
    return jsonify(row)


@bp.post("/holdings/bulk")
@jwt_required()
def bulk_holdings():
    """全量替换某实盘持仓。body: ``{portfolio_id?, rows:[{fund_code, market_value, fund_name?, cost?}]}``。"""
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status
    body = request.get_json(silent=True) or {}
    rows = body.get("rows") or []
    count = holdings_store.bulk_replace(pf["id"], uid, rows)
    return jsonify({"count": count})


@bp.delete("/holdings/<code>")
@jwt_required()
def delete_holding(code: str):
    """删除一只持仓。query: ``?portfolio_id=``。"""
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status
    holdings_store.delete_holding(pf["id"], code)
    return jsonify({"ok": True})


@bp.delete("/holdings")
@jwt_required()
def clear_holdings():
    """清空某实盘全部持仓。query: ``?portfolio_id=``。"""
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status
    holdings_store.clear_holdings(pf["id"])
    return jsonify({"ok": True})


@bp.post("/run")
@jwt_required()
def run():
    """对账。body: ``{portfolio_id, cap?, band?, sell_outside?, trim_overflow?, preset_id?}``。

    预设默认取自实盘的关联（``preset_id`` 可临时覆盖）。两个正交开关覆盖四类操作意图；
    现金由系统反推（"加满还差多少"）。返回 ``{rows, summary, meta, transfers}``。
    """
    uid = preset_access.current_user_id()
    pf, error = _resolve_portfolio(uid)
    if error:
        payload, status = error
        return jsonify(payload), status

    body = request.get_json(silent=True) or {}
    preset_id = body.get("preset_id") or pf.get("preset_id")
    if not preset_id:
        return jsonify({"rows": None, "reason": "该实盘尚未关联仓位建议，请先在上方选择一个预设"})
    if not preset_access.owned_preset(preset_id, uid):
        return jsonify({"detail": "preset not found"}), 404
    items = preset_access.snapshot_items(preset_id, uid)
    if items is None:
        return jsonify({"rows": None, "reason": "该预设尚无镜像快照，请先在筛选页保存镜像"})

    holdings = holdings_store.list_holdings(pf["id"])
    if not holdings:
        return jsonify({"rows": None, "reason": "该实盘尚未录入任何持仓，请先在上方录入"})

    cap = _clamp(body.get("cap"), CAP_MIN, CAP_MAX, optimize.DEFAULT_CAP)
    band = _clamp(body.get("band"), BAND_MIN, BAND_MAX, recon_algo.DEFAULT_BAND)
    sell_outside = bool(body.get("sell_outside"))
    trim_overflow = body.get("trim_overflow")
    trim_overflow = True if trim_overflow is None else bool(trim_overflow)

    result, clusters = compute_position(items, cap)
    if result is None or not result.get("items"):
        return jsonify({"rows": None, "reason": "有效基金不足（需 ≥3 只含股票持仓的基金），无法生成目标"})

    ind_idx = industry_crud.industry_index()
    recon = recon_algo.reconcile(result["items"], holdings, clusters, ind_idx,
                                 band=band, sell_outside=sell_outside, trim_overflow=trim_overflow)
    recon["meta"]["cap"] = cap
    recon["meta"]["preset_id"] = preset_id
    recon["meta"]["nav_as_of"] = result["meta"].get("nav_as_of")
    recon["meta"]["holdings_quarter"] = result["meta"].get("holdings_quarter")
    return jsonify(recon)
