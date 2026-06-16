import { Card, Col, Row, Statistic, Tag } from 'antd'
import type { ReconSummary } from './types'

const yuan = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 0 })

// 对账汇总卡：总资产构成 + 买卖合计 + 动作计数 + 资金约束提示
export default function SummaryCard({ summary }: { summary: ReconSummary }) {
  const c = summary.counts
  return (
    <Card size="small" title="对账汇总">
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="总资产" value={yuan(summary.total_asset)} suffix="元" />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="当前持仓" value={yuan(summary.held_total)} suffix="元" />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="可投现金" value={yuan(summary.cash)} suffix="元" />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic
            title="赛道外市值"
            value={yuan(summary.outside_value)}
            suffix="元"
            valueStyle={{ color: summary.outside_value > 0 ? '#8c8c8c' : undefined }}
          />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="建议买入合计" value={yuan(summary.buy_total)} suffix="元" valueStyle={{ color: '#fa541c' }} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="建议卖出合计" value={yuan(summary.sell_total)} suffix="元" valueStyle={{ color: '#8c8c8c' }} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="配平后剩余现金" value={yuan(summary.leftover_cash)} suffix="元" />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="缓冲带" value={(summary.band * 100).toFixed(1)} suffix="%" />
        </Col>
      </Row>
      <div style={{ marginTop: 12 }}>
        {c.open > 0 && <Tag color="volcano">建仓 {c.open}</Tag>}
        {c.add > 0 && <Tag color="orange">加仓 {c.add}</Tag>}
        {c.trim > 0 && <Tag color="default">减仓 {c.trim}</Tag>}
        {c.exit > 0 && <Tag color="default">清仓 {c.exit}</Tag>}
        {c.hold > 0 && <Tag>不动 {c.hold}</Tag>}
        {summary.scaled && (
          <Tag color="gold" style={{ marginLeft: 8 }}>
            本轮受可投资金约束，买入已等比缩减，未完全到位
          </Tag>
        )}
      </div>
    </Card>
  )
}
