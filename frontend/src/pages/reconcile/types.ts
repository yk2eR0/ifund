// 实盘对账页的数据结构（对应后端 /api/reconcile/*）

// 用户实盘持仓（持久化在 user_holdings 表）
export interface UserHolding {
  id?: number
  fund_code: string
  fund_name: string
  market_value: number   // 当前市值（元）
  updated_at?: string
}

// 对账动作：建仓 / 加仓 / 减仓 / 不动 / 清仓
export type ReconAction = 'open' | 'add' | 'trim' | 'hold' | 'exit'

// 赛道归类方式：代码命中 / 主体名命中 / 行业相似 / 赛道外 / 无持仓数据
export type ReconMatch = 'exact' | 'name' | 'similar' | 'outside' | 'no_data' | null

// 落在某赛道下的用户持仓基金
export interface ReconUserFund {
  code: string
  name: string
  market_value: number
  match: Exclude<ReconMatch, null>
  sim: number
}

export interface ReconFundRef {
  code: string
  name: string
}

// 一行对账建议（一个目标赛道，或一只赛道外基金）
export interface ReconRow {
  cluster_id: number | null
  cluster_name: string
  weight: number          // 目标占比（小数）
  target: number          // 目标市值（元）
  actual: number          // 当前市值（元）
  target_fund: ReconFundRef   // 建议操作/买入的基金
  user_funds: ReconUserFund[] // 该赛道下已持有的基金
  match: ReconMatch
  sim: number | null
  action: ReconAction
  amount: number          // 建议金额：正=买入，负=卖出
  note: string
}

export interface ReconCounts {
  open: number
  add: number
  trim: number
  hold: number
  exit: number
}

export interface ReconSummary {
  total_asset: number     // 总资产 = 持仓市值 + 可投现金
  held_total: number      // 当前持仓总市值
  cash: number            // 可投现金
  outside_value: number   // 赛道外持仓市值
  buy_total: number       // 建议买入合计
  sell_total: number      // 建议卖出合计（含清仓）
  leftover_cash: number   // 配平后剩余现金
  band: number            // 缓冲带（占总资产比例）
  scaled: boolean         // 是否因资金不足等比缩减了买入
  counts: ReconCounts
}

export interface ReconMatchCounts {
  exact: number
  name: number
  similar: number
  outside: number
  no_data: number
}

export interface ReconMeta {
  n_target_clusters: number
  match_counts: ReconMatchCounts
  outside_count: number
  cap?: number
  nav_as_of?: string | null
  holdings_quarter?: string | null
}

export interface ReconResult {
  rows: ReconRow[] | null
  summary?: ReconSummary
  meta?: ReconMeta
  reason?: string
}
