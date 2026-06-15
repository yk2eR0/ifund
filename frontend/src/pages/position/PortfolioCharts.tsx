import { Card, Col, Row, Statistic } from 'antd'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Portfolio } from './types'

// 组合净值 + 回撤走势：净值面积图（共同起点 rebase 到 1.0）叠加 underwater 回撤图，
// 二者共用同一条日期轴；数据由 /api/position/run 的 portfolio 字段下传。
export default function PortfolioCharts({ portfolio }: { portfolio: Portfolio }) {
  const { curve, max_drawdown } = portfolio
  if (!curve || curve.length < 2) return null

  const latest = curve[curve.length - 1].nav
  const totalReturn = (latest - 1) * 100
  const span = `${curve[0].date} ~ ${curve[curve.length - 1].date}`

  // "2024-03-15" → "24/03"，避免时区解析直接切片
  const fmtTick = (d: string) => `${d.slice(2, 4)}/${d.slice(5, 7)}`
  const tickGap = Math.max(1, Math.floor(curve.length / 8))

  return (
    <Card
      size="small"
      title="组合表现"
      extra={<span style={{ color: '#999', fontSize: 12 }}>{span}（按目标权重回测）</span>}
    >
      <Row gutter={16} style={{ marginBottom: 8 }}>
        <Col span={8}>
          <Statistic
            title="累计收益"
            value={totalReturn}
            precision={2}
            suffix="%"
            valueStyle={{ color: totalReturn >= 0 ? '#cf1322' : '#3f8600', fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="最大回撤"
            value={max_drawdown * 100}
            precision={2}
            suffix="%"
            valueStyle={{ color: '#3f8600', fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic title="期末净值" value={latest} precision={4} valueStyle={{ fontSize: 20 }} />
        </Col>
      </Row>

      <div style={{ fontSize: 12, color: '#888', margin: '4px 0' }}>净值走势</div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={curve} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} syncId="portfolio">
          <defs>
            <linearGradient id="navFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1677ff" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#1677ff" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tickFormatter={fmtTick} interval={tickGap} tick={{ fontSize: 11, fill: '#999' }} minTickGap={16} />
          <YAxis domain={['auto', 'auto']} tickFormatter={(v) => v.toFixed(2)} width={48} tick={{ fontSize: 11, fill: '#999' }} />
          <Tooltip
            labelFormatter={(d) => `日期 ${d}`}
            formatter={(v: number) => [v.toFixed(4), '组合净值']}
            contentStyle={{ fontSize: 12 }}
          />
          <Area type="monotone" dataKey="nav" stroke="#1677ff" strokeWidth={1.6} fill="url(#navFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>

      <div style={{ fontSize: 12, color: '#888', margin: '8px 0 4px' }}>回撤走势（underwater）</div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={curve} margin={{ top: 4, right: 12, left: 0, bottom: 0 }} syncId="portfolio">
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ff4d4f" stopOpacity={0.06} />
              <stop offset="100%" stopColor="#ff4d4f" stopOpacity={0.3} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tickFormatter={fmtTick} interval={tickGap} tick={{ fontSize: 11, fill: '#999' }} minTickGap={16} />
          <YAxis domain={['auto', 0]} tickFormatter={(v) => `${v}%`} width={48} tick={{ fontSize: 11, fill: '#999' }} />
          <Tooltip
            labelFormatter={(d) => `日期 ${d}`}
            formatter={(v: number) => [`${v.toFixed(2)}%`, '回撤']}
            contentStyle={{ fontSize: 12 }}
          />
          <Area type="monotone" dataKey="drawdown" stroke="#ff4d4f" strokeWidth={1.2} fill="url(#ddFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  )
}
