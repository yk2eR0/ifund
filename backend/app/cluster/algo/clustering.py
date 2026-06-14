"""纯 numpy 凝聚聚类（Lance-Williams Ward），切到指定簇数。

等价于 scipy ``linkage(method='ward')`` + ``fcluster(criterion='maxclust')``，但不依赖 scipy
（其 C 扩展会破坏本项目 pylint 满分）。规模 n<200，O(n³) 可忽略。
"""
from __future__ import annotations

import numpy as np  # pylint: disable=import-error


def _closest_pair(dist: np.ndarray, active: np.ndarray) -> tuple[int, int]:
    """返回当前活跃簇中距离最小的一对下标 ``(i, j)``，i<j。"""
    masked = np.where(active[:, None] & active[None, :], dist, np.inf)
    np.fill_diagonal(masked, np.inf)
    flat = int(np.argmin(masked))
    i, j = divmod(flat, masked.shape[1])
    return (i, j) if i < j else (j, i)


def fcluster_ward(dist: np.ndarray, target: int) -> list[int]:
    """对距离矩阵做 Ward 凝聚聚类，合并到 ``target`` 簇，返回每点的簇号（1..k）。"""
    n = dist.shape[0]
    target = max(1, min(target, n))
    dist = dist.astype(float).copy()
    size = np.ones(n, dtype=float)
    active = np.ones(n, dtype=bool)
    members: list[list[int]] = [[p] for p in range(n)]

    clusters = n
    while clusters > target:
        i, j = _closest_pair(dist, active)
        ni, nj = size[i], size[j]
        for k in range(n):
            if not active[k] or k in (i, j):
                continue
            nk = size[k]
            new = np.sqrt(
                ((ni + nk) * dist[i, k] ** 2 + (nj + nk) * dist[j, k] ** 2
                 - nk * dist[i, j] ** 2) / (ni + nj + nk))
            dist[i, k] = dist[k, i] = new
        size[i] = ni + nj
        members[i].extend(members[j])
        members[j] = []
        active[j] = False
        clusters -= 1

    labels = [0] * n
    for cluster_id, idx in enumerate((p for p in range(n) if active[p]), start=1):
        for point in members[idx]:
            labels[point] = cluster_id
    return labels
