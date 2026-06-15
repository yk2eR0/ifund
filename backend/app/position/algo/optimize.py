"""组合优化：每簇 TOP5 候选交叉组合 + 行业集中度约束。

聚类按行业聚类，导致多簇主行业相同（如「通信」），每簇取 TOP1 后穿透到底层
高度重合、相关性强、易同涨同跌。本模块用两阶段贪心 / 局部搜索缓解：

1. 选基金：每簇从 TOP5 候选里选 1 只，在保证综合分（质量）尽量高的前提下，
   尽量降低组合的单一行业穿透占比（弱杠杆，仅当簇内有更分散的次优基金时生效）。
2. 权重再分配：在景气度×乖离的基准权重上，把权重从「贡献高集中行业」的簇挪向
   其它簇，使最大单一行业穿透占比不超过 cap（主杠杆）。

行业占比 = 某行业穿透暴露 / 全部股票穿透暴露（相对份额，与前端 lookthrough 口径一致）。
cap 作为硬上限用大惩罚松弛实现：可行域内纯最大化质量，超限被强力拉回。
"""
from __future__ import annotations

TOPK = 5            # 每簇候选数
WMIN, WMAX = 0.03, 0.25   # 单簇权重上下限（与 target_weights 截断一致）
DEFAULT_CAP = 0.18  # 单一行业穿透占比上限（中等均衡）
_PENALTY = 12.0     # 超过 cap 的惩罚强度（质量量纲 0~1，足够强即可压回可行域）


def _max_industry_share(vecs: list[dict], w: list[float]) -> float:
    """组合最大单一行业穿透占比 = 最大行业暴露 / 全部行业暴露。"""
    expo: dict[str, float] = {}
    for vec, wc in zip(vecs, w):
        for lab, v in vec.items():
            expo[lab] = expo.get(lab, 0.0) + wc * v
    total = sum(expo.values())
    return (max(expo.values()) / total) if total > 0 else 0.0


def select_funds(cands: list[list[dict]], cap: float = DEFAULT_CAP) -> list[int]:
    """每簇从候选里选 1 只：maximize 平均质量 − 惩罚·max(0, 行业占比 − cap)。

    cands[c] 为该簇候选列表（按综合分降序，[0]=TOP1），每个候选含 ``score`` 与
    ``vec``（行业→占净值%）。返回 choice[c] = 选中候选下标。
    """
    n = len(cands)
    if n == 0:
        return []
    all_scores = [f["score"] for cl in cands for f in cl]
    lo, hi = min(all_scores), max(all_scores)
    rng = (hi - lo) or 1.0

    def quality(f: dict) -> float:
        return (f["score"] - lo) / rng   # 全局 min-max 归一，跨簇可比

    def objective(choice: list[int]) -> float:
        vecs = [cands[c][choice[c]]["vec"] for c in range(n)]
        avg_q = sum(quality(cands[c][choice[c]]) for c in range(n)) / n
        share = _max_industry_share(vecs, [1.0 / n] * n)   # 选基金阶段等权评估
        return avg_q - _PENALTY * max(0.0, share - cap)

    choice = [0] * n   # 从每簇 TOP1 出发
    best = objective(choice)
    improved = True
    while improved:
        improved = False
        for c in range(n):
            cur = choice[c]
            for k in range(len(cands[c])):
                if k == cur or not cands[c][k]["vec"]:
                    continue
                choice[c] = k
                val = objective(choice)
                if val > best + 1e-9:
                    best, cur, improved = val, k, True
                else:
                    choice[c] = cur
    return choice


def rebalance_weights(base: list[float], vecs: list[dict], quality: list[float],
                      cap: float = DEFAULT_CAP, step: float = 0.005) -> list[float]:
    """在基准权重上做行业感知再分配：maximize Σ w·quality − 惩罚·max(0, 行业占比 − cap)。

    base：景气度×乖离得到的基准权重（已截断到 [WMIN, WMAX] 并归一）；
    vecs：各簇选中基金的行业向量；quality：各簇质量（归一景气度，0~1）。
    用「从一簇挪 step 给另一簇」的局部搜索，始终满足 ∑w=1、w∈[WMIN,WMAX]。
    """
    n = len(base)
    if n < 2:
        return list(base)
    w = list(base)

    def objective(ww: list[float]) -> float:
        share = _max_industry_share(vecs, ww)
        return sum(ww[c] * quality[c] for c in range(n)) - _PENALTY * max(0.0, share - cap)

    best = objective(w)
    for _ in range(800):
        improved = False
        for i in range(n):
            for j in range(n):
                if i == j or w[i] - step < WMIN or w[j] + step > WMAX:
                    continue
                w[i] -= step
                w[j] += step
                val = objective(w)
                if val > best + 1e-9:
                    best, improved = val, True
                else:
                    w[i] += step
                    w[j] -= step
        if not improved:
            break

    total = sum(w) or 1.0
    return [round(x / total, 4) for x in w]
