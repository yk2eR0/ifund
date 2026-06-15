// 仓位建议页的数据结构（对应后端 /api/position/run 返回）

export interface ProsperityBreakdown {
  total: number
  momentum: number
  risk_adj: number
  breadth: number
  consistency: number
}

export interface DeviationInfo {
  d20: number
  d60: number
  combined: number
}

export interface PositionFund {
  code: string
  name: string
  score: number
  sharpe_3y: number | null
  scale: number | null
}

export interface PositionIndustry {
  label: string
  ratio: number
}

export interface Recommendation {
  tag: string
  reason: string
}

export interface PositionItem {
  cluster_id: number
  cluster_name: string
  top_industries: PositionIndustry[]
  fund_count: number
  fund: PositionFund
  nav_points: number
  prosperity: ProsperityBreakdown
  deviation: DeviationInfo
  base_weight: number
  weight: number
  recommendation: Recommendation
}

export interface PositionMeta {
  n_clusters: number
  base_weight: number
  nav_missing: string[]
}

export interface ClusterMetaBrief {
  n: number
  dropped: number
  total: number
  t: number
  target: number
}

export interface PortfolioPoint {
  date: string       // 交易日 YYYY-MM-DD
  nav: number        // 组合净值（共同起点 rebase 到 1.0）
  drawdown: number   // 相对历史峰值的回撤，负百分比（如 -5.2）
}

export interface Portfolio {
  curve: PortfolioPoint[]
  max_drawdown: number   // 最大回撤（正小数，如 0.23 表示 23%）
}

export interface PositionResult {
  items: PositionItem[] | null
  portfolio?: Portfolio
  meta?: PositionMeta
  cluster_meta?: ClusterMetaBrief
  reason?: string
}
