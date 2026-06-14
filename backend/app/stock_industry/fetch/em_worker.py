#!/usr/bin/env python3
"""东财兜底 worker：校正海外误判 + 补港股行业。

申万体系只含 A 股。本 worker 做两件事：
1. **校正市场**：用 A 股全集（``stock_info_a_code_name``）把「6 位数字但不在全集」的持仓
   （韩股如 005930 三星、或已退市）改判 market=OTHER（归海外/其他）；
2. **补港股**：``stock_hk_company_profile_em`` 取「所属行业」写 em_industry（datacenter 域名，可直连）。

A 股缺口（北交所 920 段 + 个别特钢）不走东财：其个股接口在 push2 域名、常被网络策略拦截，
且北交所在申万体系外。这部分留「未覆盖」，由人工修正处理。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND_DIR = os.getenv("IFUND_BACKEND_DIR") or str(Path(__file__).resolve().parents[3])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
os.chdir(_BACKEND_DIR)

# pylint: disable=wrong-import-position
import time

import akshare as ak  # pylint: disable=import-error

from app import db as database
from app.common import worker_base
from app.stock_industry.crud import industry_crud

SLEEP_SEC = 0.6


def _log(msg: str) -> None:
    """worker 子进程 stderr 被父进程 DEVNULL 吞掉，关键诊断信息单独落文件。"""
    path = Path(_BACKEND_DIR) / "logs" / "industry_worker.log"
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"[em] {msg}\n")


def _a_master() -> set[str]:
    """A 股代码全集（用于把误判成 A 股的韩股/退市剔出）；失败返回空集（则不校正）。"""
    try:
        return set(ak.stock_info_a_code_name()["code"].astype(str))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _log(f"获取 A 股全集失败（本轮跳过市场校正）：{exc}")
        return set()


def _hk_industry(code: str) -> str:
    """港股「所属行业」：东财港股公司资料（宽表单行，取「所属行业」列）。"""
    try:
        frame = ak.stock_hk_company_profile_em(symbol=code)
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    if frame is None or frame.empty or "所属行业" not in frame.columns:
        return ""
    return str(frame["所属行业"].iloc[0] or "").strip()


def _is_terminated(task_id: int) -> bool:
    task = database.select_one("fetch_tasks", {"id": f"eq.{task_id}"})
    return task is None or task.get("status") == "terminated"


def _reclassify_overseas(held, names) -> int:
    """把「6 位数字但不在 A 股全集」的持仓改判海外（韩股/退市）；离线，不计采集进度。"""
    master = _a_master()
    if not master:
        return 0
    moved = 0
    for code in industry_crud.uncovered_held(held, markets=("A",)):
        if code not in master:
            industry_crud.upsert_industry(code, names.get(code, ""), market="OTHER")
            moved += 1
    return moved


def run(task_id: int) -> None:
    """先校正海外误判，再补未覆盖港股的行业。"""
    held = industry_crud.held_codes()
    names = industry_crud.held_names()

    moved = _reclassify_overseas(held, names)
    targets = industry_crud.uncovered_held(held, markets=("HK",))
    _log(f"改判海外 {moved} 只；待补港股 {len(targets)} 只")

    database.update("fetch_tasks", {"id": task_id}, {"target_count": len(targets)})
    success = fail = current = 0
    terminated = False
    for code in targets:
        current += 1
        industry = _hk_industry(code)
        if industry:
            industry_crud.upsert_industry(
                code, names.get(code, ""), market="HK", em=industry, source="eastmoney")
            success += 1
        else:
            fail += 1
        database.update("fetch_tasks", {"id": task_id}, {
            "current_count": current, "success_count": success, "fail_count": fail,
        })
        if _is_terminated(task_id):
            terminated = True
            break
        time.sleep(SLEEP_SEC)
    database.update("fetch_tasks", {"id": task_id},
                    {"status": "terminated" if terminated else "finished"})


if __name__ == "__main__":
    _task_id, _, _ = worker_base.parse_args(sys.argv[1:])
    try:
        run(_task_id)
    except Exception as _exc:  # pylint: disable=broad-exception-caught
        _log(f"worker 异常退出：{_exc}")
        database.update("fetch_tasks", {"id": _task_id}, {"status": "terminated"})
        raise
