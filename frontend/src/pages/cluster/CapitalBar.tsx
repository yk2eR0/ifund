import { Tooltip } from 'antd'
import type { CapitalStock } from './types'

// 簇实际资金暴露条形：按占簇内总重仓市值的比例排布（规模加权，绿色区别于行业蓝条）
export default function CapitalBar({ stocks }: { stocks: CapitalStock[] }) {
  if (!stocks.length) return null
  const max = Math.max(...stocks.map((s) => s.mv_pct), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {stocks.map((s) => (
        <div key={s.code} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 150, fontSize: 12, textAlign: 'right' }} title={s.name}>
            {s.name}
          </span>
          <div style={{ flex: 1, background: 'rgba(140,140,140,0.18)', borderRadius: 3, height: 14 }}>
            <Tooltip title={`${s.industry} · 簇内 ${s.overlap} 只基金持有`}>
              <div
                style={{
                  width: `${(s.mv_pct / max) * 100}%`,
                  background: '#52c41a',
                  height: '100%',
                  borderRadius: 3,
                }}
              />
            </Tooltip>
          </div>
          <span style={{ width: 130, fontSize: 12 }}>
            {s.mv_yi.toFixed(2)} 亿 · {s.mv_pct.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  )
}
