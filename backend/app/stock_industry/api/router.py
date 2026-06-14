"""股票→行业映射蓝图：申万/东财两种采集任务 + 覆盖率/列表/聚合查询 + 人工修正。

读端点公开（后端绑定 127.0.0.1，与现有 task/running 等只读端点一致）；
写端点（触发采集、终止、人工修正）需 JWT。
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import db as database
from app.common import sync_launcher, task_support
from app.stock_industry.crud import industry_crud

_FETCH_DIR = Path(__file__).resolve().parents[1] / "fetch"
SW_WORKER = str(_FETCH_DIR / "sw_worker.py")
EM_WORKER = str(_FETCH_DIR / "em_worker.py")
SW_TASK = "fetch_sw_industry"
EM_TASK = "fetch_em_industry"

bp = Blueprint("stock_industry", __name__, url_prefix="/api/stock_industry")


def _start(task_type: str, worker: str, codes=None):
    if task_support.get_running(task_type):
        return jsonify({"detail": "已有运行中的任务"}), 409
    try:
        task_id = sync_launcher.start_sync_task(task_type, worker, codes=codes)
    except database.UniqueViolation:
        return jsonify({"detail": "已有运行中的任务"}), 409
    return jsonify({"task_id": task_id})


@bp.post("/sync/sw")
@jwt_required()
def sync_sw():
    """触发申万三级采集（legulegu）。可选 ?codes=行业代码,逗号分隔 只重采指定行业。"""
    raw = request.args.get("codes", "")
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    return _start(SW_TASK, SW_WORKER, codes=codes)


@bp.post("/sync/em")
@jwt_required()
def sync_em():
    """触发东财兜底采集（补申万未覆盖的持仓股票，主要是港股）。"""
    return _start(EM_TASK, EM_WORKER)


@bp.get("/task/running")
def task_running():
    """查询采集任务运行状态。?type=sw|em（默认 sw）。"""
    task_type = EM_TASK if request.args.get("type") == "em" else SW_TASK
    return jsonify(task_support.get_running(task_type))


@bp.post("/task/<int:task_id>/terminate")
@jwt_required()
def terminate(task_id):
    """终止采集任务。"""
    return task_support.terminate_flow("stock_industry", task_id)


@bp.post("/terminate")
def remote_terminate():
    """跨机终止接收端。"""
    return task_support.remote_terminate()


@bp.get("/stats")
def stats():
    """覆盖率统计（针对持仓股票）。"""
    return jsonify(industry_crud.stats())


@bp.get("/breakdown")
def breakdown():
    """持仓股票按聚类标签聚合计数。?top=N 仅返回前 N。"""
    top = int(request.args.get("top", 0) or 0)
    return jsonify(industry_crud.breakdown(top))


@bp.get("/list")
def list_mapping():
    """分页列出持仓股票的行业映射，支持市场/覆盖状态/行业关键词/代码名称筛选。"""
    page = max(int(request.args.get("page", 1) or 1), 1)
    page_size = min(max(int(request.args.get("page_size", 50) or 50), 1), 500)
    total, items = industry_crud.list_page(
        market=request.args.get("market", ""),
        label_kw=request.args.get("label", ""),
        status=request.args.get("status", ""),
        keyword=request.args.get("keyword", ""),
        skip=(page - 1) * page_size, limit=page_size,
    )
    return jsonify({"total": total, "items": items, "page": page, "page_size": page_size})


@bp.put("/manual/<code>")
@jwt_required()
def manual(code):
    """人工修正某只股票的行业标签（之后采集不再覆盖）。"""
    data = request.get_json(silent=True) or {}
    industry_crud.set_manual(code, data)
    return jsonify({"ok": True})
