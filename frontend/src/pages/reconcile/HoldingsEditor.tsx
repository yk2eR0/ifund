import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Button, Card, Empty, Input, InputNumber, Popconfirm, Space, Table, Typography, message,
} from 'antd'
import { DeleteOutlined, ImportOutlined, ReloadOutlined } from '@ant-design/icons'
import request from '../../api/request'
import type { UserHolding } from './types'

const { TextArea } = Input

// 持仓录入：表格行内改市值/删除 + 批量粘贴导入（每行「代码<分隔>金额」）。
// 持仓持久化在后端 user_holdings 表，跨会话保留；改动后回调 onChanged 通知父组件重算可投。
export default function HoldingsEditor({ onChanged }: { onChanged?: () => void }) {
  const [items, setItems] = useState<UserHolding[]>([])
  const [loading, setLoading] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const [importing, setImporting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await request.get<{ items: UserHolding[] }>('/reconcile/holdings')
      setItems(data.items ?? [])
    } catch {
      message.error('加载持仓失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // 行内改市值：失焦即 upsert
  const saveValue = async (code: string, name: string, mv: number) => {
    try {
      await request.post('/reconcile/holdings', { fund_code: code, fund_name: name, market_value: mv })
      onChanged?.()
    } catch {
      message.error('保存失败')
      load()
    }
  }

  const removeHolding = async (code: string) => {
    try {
      await request.delete(`/reconcile/holdings/${code}`)
      setItems((prev) => prev.filter((h) => h.fund_code !== code))
      onChanged?.()
    } catch {
      message.error('删除失败')
    }
  }

  // 粘贴导入：每行「代码<分隔>金额」，分隔符可为 tab/逗号/中文逗号/空白。全量替换。
  const doImport = async () => {
    const rows = pasteText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split(/[\t,，\s]+/).filter(Boolean)
        const code = parts[0]
        const mv = Number(parts[parts.length - 1])
        return { fund_code: code, market_value: Number.isFinite(mv) ? mv : 0 }
      })
      .filter((r) => r.fund_code && r.market_value > 0)
    if (rows.length === 0) {
      message.warning('未解析到有效行（格式：基金代码 金额，每行一只）')
      return
    }
    setImporting(true)
    try {
      const { data } = await request.post<{ count: number }>('/reconcile/holdings/bulk', { rows })
      message.success(`已导入 ${data.count} 只（全量替换）`)
      setPasteText('')
      await load()
      onChanged?.()
    } catch {
      message.error('导入失败')
    } finally {
      setImporting(false)
    }
  }

  const total = items.reduce((s, h) => s + (h.market_value || 0), 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card
        size="small"
        title={`实盘持仓（共 ${items.length} 只 · 合计 ${total.toLocaleString('zh-CN', { maximumFractionDigits: 0 })} 元）`}
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
        }
      >
        {items.length === 0 ? (
          <Empty description="暂无持仓，请在下方粘贴导入" />
        ) : (
          <Table
            size="small"
            rowKey="fund_code"
            loading={loading}
            dataSource={items}
            pagination={false}
            columns={[
              {
                title: '基金编码',
                dataIndex: 'fund_code',
                width: 120,
                render: (v: string) => <span style={{ fontFamily: 'monospace' }}>{v}</span>,
              },
              { title: '基金名称', dataIndex: 'fund_name', render: (v: string) => v || <Typography.Text type="secondary">—</Typography.Text> },
              {
                title: '当前市值（元）',
                dataIndex: 'market_value',
                width: 180,
                align: 'right',
                render: (v: number, row) => (
                  <InputNumber
                    value={v}
                    min={0}
                    precision={2}
                    style={{ width: 150 }}
                    formatter={(x) => `${x}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={(x) => Number((x || '').replace(/,/g, ''))}
                    onBlur={(e) => {
                      const mv = Number((e.target.value || '').replace(/,/g, ''))
                      if (Number.isFinite(mv) && mv !== v) saveValue(row.fund_code, row.fund_name, mv)
                    }}
                  />
                ),
              },
              {
                title: '操作',
                width: 70,
                align: 'center',
                render: (_, row) => (
                  <Popconfirm title="删除该持仓？" onConfirm={() => removeHolding(row.fund_code)}>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Card size="small" title="批量粘贴导入">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="每行一只基金，格式「基金代码 金额」，分隔符支持空格 / 逗号 / Tab。可直接从 Excel 复制两列粘贴。导入为全量替换（覆盖现有持仓）。"
          />
          <TextArea
            rows={6}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder={'示例：\n000001 30000\n110011,15000\n005827\t8000'}
          />
          <Button type="primary" icon={<ImportOutlined />} loading={importing} onClick={doImport}>
            解析并导入
          </Button>
        </Space>
      </Card>
    </div>
  )
}
