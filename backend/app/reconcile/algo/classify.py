"""把用户持仓基金归类到「赛道（聚类簇）」。

三级匹配，越靠前越可信：
1. **exact**：基金代码命中某簇成员 → 直接归该簇（聚类簇 ``funds`` 含全部成员，O(1) 查表）。
2. **name**：去份额后缀的主体名命中（解决「用户持的是被 A/C 去重剔除的份额」漏查）。
3. **similar**：用前十大持仓的行业向量与各簇行业向量做 Bray-Curtis 相似度，argmax 且
   ≥ 阈值才归类（赛道外基金的兜底），否则判 outside。无持仓数据则判 no_data（无法归类）。

行业向量复用 ③ 仓位的口径（前十大按申万行业聚合占净值%）；相似度复用聚类的
Bray-Curtis（各自归一化后逐 key 取 min 求和，范围 [0,1]）。
"""
from __future__ import annotations

from app.cluster.algo.dedup import _base_name
from app.fund_holdings.crud import holdings_crud
from app.position.algo.pipeline import _industry_vector

SIM_THRESHOLD = 0.35   # Bray-Curtis 相似度归类阈值（经验值；top_industries 稀疏，宁可判 outside）


def build_code_to_cluster(clusters: list[dict]) -> dict[str, int]:
    """``{基金代码: cluster_id}``：簇内全部成员（非仅代表基金）。"""
    out: dict[str, int] = {}
    for c in clusters:
        for f in c.get("funds", []):
            code = (f.get("code") or "").strip()
            if code:
                out[code] = c["cluster_id"]
    return out


def build_name_index(clusters: list[dict]) -> dict[str, int]:
    """``{主体名(去份额后缀): cluster_id}``：兜底匹配被 A/C 去重剔除的份额。

    同名冲突时保留首次出现（簇按基金数降序，大簇优先），影响极小。
    """
    out: dict[str, int] = {}
    for c in clusters:
        for f in c.get("funds", []):
            base = _base_name(f.get("name") or "")
            if base and base not in out:
                out[base] = c["cluster_id"]
    return out


def cluster_vectors(clusters: list[dict]) -> dict[int, dict[str, float]]:
    """各簇行业向量 ``{cluster_id: {行业: 占比}}``，取自 ``cluster["top_industries"]``。"""
    return {c["cluster_id"]: {i["label"]: i["ratio"] for i in c.get("top_industries", [])}
            for c in clusters}


def _normalize(vec: dict[str, float]) -> dict[str, float]:
    total = sum(vec.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in vec.items()}


def bray_curtis_sim(a: dict[str, float], b: dict[str, float]) -> float:
    """两行业向量各自归一化后逐 key 取 min 求和（Bray-Curtis 相似度，范围 [0,1]）。"""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    return sum(min(na[k], nb.get(k, 0.0)) for k in na)


def classify_fund(code: str, fund_name: str,
                  code2cluster: dict[str, int], name2cluster: dict[str, int],
                  cluster_vecs: dict[int, dict[str, float]], ind_idx: dict) -> tuple:
    """归类单只基金，返回 ``(cluster_id|None, match, sim)``。

    match ∈ {exact, name, similar, outside, no_data}。outside=有行业数据但都不够像；
    no_data=库里没采过该基金持仓（无法归类，前端单独提示）。
    """
    code = (code or "").strip()
    if code in code2cluster:
        return code2cluster[code], "exact", 1.0

    base = _base_name(fund_name or "")
    if base and base in name2cluster:
        return name2cluster[base], "name", 1.0

    holdings = holdings_crud.top_holdings(code, "stock")
    vec = _industry_vector(holdings, ind_idx)
    if not vec:
        return None, "no_data", 0.0

    best_cid, best_sim = None, 0.0
    for cid, cvec in cluster_vecs.items():
        sim = bray_curtis_sim(vec, cvec)
        if sim > best_sim:
            best_cid, best_sim = cid, sim
    if best_cid is not None and best_sim >= SIM_THRESHOLD:
        return best_cid, "similar", round(best_sim, 3)
    return None, "outside", round(best_sim, 3)
