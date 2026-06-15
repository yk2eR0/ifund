import { Card, Col, Row, Statistic, Table, Tag, Tooltip, theme } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Lookthrough, LookthroughStock } from './types'

// 底层持仓穿透：把各簇代表基金的前十大股票按目标权重累加，
// 用于人工 Review——重叠越多说明底层越集中、代表基金相关性越高。
export default function LookthroughCard({ data }: { data: Lookthrough }) {
  const { token } = theme.useToken()

  const fundList = (s: LookthroughStock) => (
    <div style={{ maxWidth: 240 }}>
      {s.funds.map((f, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, lineHeight: '18px' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
          <span style={{ flexShrink: 0 }}>{f.ratio}%</span>
        </div>
      ))}
    </div>
  )

  const columns: ColumnsType<LookthroughStock> = [
    {
      title: '股票',
      dataIndex: 'name',
      render: (v: string, r) => (
        <span>
          {v} <span style={{ color: token.colorTextTertiary, fontSize: 12 }}>{r.code}</span>
        </span>
      ),
    },
    {
      title: '组合穿透仓位',
      dataIndex: 'exposure',
      align: 'right',
      width: 130,
      defaultSortOrder: 'descend',
      sorter: (a, b) => a.exposure - b.exposure,
      render: (v: number) => (
        <b style={{ color: v >= 3 ? '#f5222d' : token.colorText }}>{v.toFixed(2)}%</b>
      ),
    },
    {
      title: '持有基金',
      dataIndex: 'fund_count',
      align: 'center',
      width: 120,
      sorter: (a, b) => a.fund_count - b.fund_count,
      render: (v: number, r) => (
        <Tooltip title={fundList(r)} placement="left">
          {v >= 2 ? <Tag color="orange">{v} 只重叠</Tag> : <span>{v} 只</span>}
        </Tooltip>
      ),
    },
  ]

  return (
    <Card size="small" title="底层持仓穿透（前十大股票累计）">
      <Row gutter={16} style={{ marginBottom: 8 }}>
        <Col span={6}>
          <Statistic title="覆盖代表基金" value={data.funds_covered} suffix="只" valueStyle={{ fontSize: 20 }} />
        </Col>
        <Col span={6}>
          <Statistic title="累计不同股票" value={data.total_stocks} suffix="只" valueStyle={{ fontSize: 20 }} />
        </Col>
        <Col span={6}>
          <Statistic
            title="重叠股票"
            value={data.overlap_stocks}
            suffix="只"
            valueStyle={{ fontSize: 20, color: data.overlap_stocks ? '#fa8c16' : token.colorText }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="前十大穿透总仓位"
            value={data.visible_position}
            precision={2}
            suffix="%"
            valueStyle={{ fontSize: 20 }}
          />
        </Col>
      </Row>
      <div style={{ fontSize: 12, color: token.colorTextTertiary, marginBottom: 8 }}>
        穿透仓位 = ∑（基金目标权重 × 该基金中此股占净值比例）。重叠越多 → 底层实际越集中、代表基金相关性越高。仅含可见前十大持仓，非完整持仓。
      </div>
      <Table<LookthroughStock>
        size="small"
        rowKey="code"
        columns={columns}
        dataSource={data.stocks}
        pagination={{ pageSize: 10, size: 'small', showSizeChanger: false }}
      />
    </Card>
  )
}
