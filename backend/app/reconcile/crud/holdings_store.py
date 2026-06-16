"""用户实盘持仓（``user_holdings`` 表）读写：按 user_id 隔离，每只基金一行。

录入是重活、跨会话保留，故持久化；现金 / 缓冲带 / cap 是即时计算参数走请求体不落库
（持久化会陈旧误导）。名称缺失时从 ``funds`` 表补全。
"""
from __future__ import annotations

import datetime

from app import db as database

TABLE = "user_holdings"


def _now() -> str:
    return datetime.datetime.now().isoformat()


def list_holdings(uid: int) -> list[dict]:
    """该用户全部持仓，按市值降序。"""
    return database.select(TABLE, {
        "user_id": f"eq.{uid}", "order": "market_value.desc",
    })


def _fund_name(code: str) -> str:
    """从 funds 表取基金名（用于录入时未提供名称的兜底）。"""
    row = database.select_one("funds", {"code": f"eq.{code}"})
    return row.get("name", "") if row else ""


def upsert_holding(uid: int, code: str, name: str, mv: float) -> dict:
    """upsert 单只持仓；name 为空则从 funds 表补。返回该行。"""
    code = (code or "").strip()
    name = (name or "").strip() or _fund_name(code)
    existing = database.select_one(TABLE, {
        "user_id": f"eq.{uid}", "fund_code": f"eq.{code}",
    })
    fields = {"fund_name": name, "market_value": mv, "updated_at": _now()}
    if existing:
        database.update(TABLE, {"user_id": uid, "fund_code": code}, fields)
        return {**existing, **fields}
    return database.insert(TABLE, {"user_id": uid, "fund_code": code, **fields})


def bulk_replace(uid: int, rows: list[dict]) -> int:
    """全量替换该用户持仓：先删后批量插入。

    rows 每项 ``{fund_code, market_value, fund_name?}``；同一 code 取最后一条（去重）。
    名称缺失从 funds 表补。返回写入行数。
    """
    cleaned: dict[str, dict] = {}
    for r in rows:
        code = str(r.get("fund_code") or "").strip()
        if not code:
            continue
        try:
            mv = float(r.get("market_value") or 0)
        except (TypeError, ValueError):
            continue
        cleaned[code] = {"fund_code": code, "market_value": mv,
                         "fund_name": (r.get("fund_name") or "").strip()}

    database.delete(TABLE, {"user_id": uid})
    if not cleaned:
        return 0
    now = _now()
    payload = [{
        "user_id": uid, "fund_code": c,
        "fund_name": v["fund_name"] or _fund_name(c),
        "market_value": v["market_value"], "updated_at": now,
    } for c, v in cleaned.items()]
    database.batch_insert(TABLE, payload)
    return len(payload)


def delete_holding(uid: int, code: str) -> None:
    """删除该用户的一只持仓。"""
    database.delete(TABLE, {"user_id": uid, "fund_code": (code or "").strip()})


def clear_holdings(uid: int) -> None:
    """清空该用户全部持仓。"""
    database.delete(TABLE, {"user_id": uid})
