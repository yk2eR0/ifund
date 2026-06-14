"""Bray-Curtis 相似度 → 股票/行业融合 → 距离矩阵。

行归一化到和为 1 后，Bray-Curtis 相似度退化为 ``sum_k min(a_ik, a_jk)``（范围 [0,1]）。
融合 ``sim = 0.6·sim_stk + 0.4·sim_ind``，映射到带符号空间 ``2·sim-1`` 后取距离
``dist = 1 - (2·sim-1) = 2(1-sim)``（范围 [0,2]）。
"""
from __future__ import annotations

import numpy as np  # pylint: disable=import-error

W_STK = 0.6
W_IND = 0.4


def _row_normalize(mat: np.ndarray) -> np.ndarray:
    """各行除以行和；全零行保持全零（不产生 NaN）。"""
    sums = mat.sum(axis=1, keepdims=True)
    safe = np.where(sums == 0, 1.0, sums)
    return mat / safe


def _bray_curtis(mat: np.ndarray) -> np.ndarray:
    """归一化矩阵的逐对 Bray-Curtis 相似度（= 逐列取小后求和）。"""
    return np.minimum(mat[:, None, :], mat[None, :, :]).sum(axis=2)


def distance_matrix(stk_matrix: np.ndarray, ind_matrix: np.ndarray) -> np.ndarray:
    """融合股票/行业相似度，返回对称距离矩阵（对角为 0）。"""
    sim_stk = _bray_curtis(_row_normalize(stk_matrix))
    sim_ind = _bray_curtis(_row_normalize(ind_matrix))
    sim = W_STK * sim_stk + W_IND * sim_ind
    dist = 1.0 - (2.0 * sim - 1.0)
    dist = (dist + dist.T) / 2.0       # 抹平浮点不对称
    np.fill_diagonal(dist, 0.0)
    return dist
