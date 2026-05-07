import React from 'react'
import { ENTITY_CONFIG } from './entityConfig'

const RELATIONS = [
  { label: 'belongs_to',  from: 'Task',    to: 'Projeto'  },
  { label: 'assigned_to', from: 'Task',    to: 'Pessoa'   },
  { label: 'threatens',   from: 'Risco',   to: 'Projeto'  },
  { label: 'answers',     from: 'Decisão', to: 'Pergunta' },
  { label: 'member_of',   from: 'Pessoa',  to: 'Projeto'  },
]

export function GraphLegend() {
  return (
    <div style={{ padding: '16px 14px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <p style={{ margin: '0 0 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9CA3AF' }}>
          Entidades
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Object.entries(ENTITY_CONFIG).map(([type, cfg]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: cfg.light, border: `1px solid ${cfg.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, flexShrink: 0,
              }}>
                {cfg.icon}
              </div>
              <div>
                <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: cfg.color }}>{cfg.label}</p>
                <p style={{ margin: 0, fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace' }}>{type}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p style={{ margin: '0 0 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9CA3AF' }}>
          Relações
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {RELATIONS.map((r) => (
            <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#FF791F', flexShrink: 0 }} />
              <div>
                <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#FF791F', fontWeight: 600 }}>{r.label}</span>
                <span style={{ fontSize: 10, color: '#9CA3AF', marginLeft: 6 }}>{r.from} → {r.to}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
