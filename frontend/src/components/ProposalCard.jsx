import React from 'react'
import { PRIORITY_COLORS } from './entityConfig'

const ICONS = {
  orphan_task:       '👤',
  overdue_task:      '⏰',
  critical_risk:     '🚨',
  answered_question: '✅',
  spof:              '⚡',
  stale_question:    '🔁',
}

const PRIORITY_LABELS = {
  critical: 'Crítico',
  high:     'Alto',
  medium:   'Médio',
  low:      'Baixo',
}

export function ProposalCard({ proposal }) {
  const color = PRIORITY_COLORS[proposal.priority] || '#9CA3AF'
  const icon  = ICONS[proposal.type] || '📋'

  return (
    <div style={{
      borderRadius: 10,
      background: '#ffffff',
      border: `1px solid #EDE8E0`,
      borderLeft: `3px solid ${color}`,
      padding: '10px 12px',
      display: 'flex', flexDirection: 'column', gap: 7,
      boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span style={{ fontSize: 15, lineHeight: 1, marginTop: 1, flexShrink: 0 }}>{icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: '#1A1A2E', lineHeight: 1.4 }}>
            {proposal.title}
          </p>
          <p style={{ margin: '3px 0 0', fontSize: 11, color: '#6B7280', lineHeight: 1.5 }}>
            {proposal.description}
          </p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
          textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99,
          background: `${color}15`, color, border: `1px solid ${color}30`,
        }}>
          {PRIORITY_LABELS[proposal.priority] || proposal.priority}
        </span>
        <span style={{ fontSize: 10, color: '#9CA3AF' }}>
          {proposal.entity_type} · {proposal.entity_title}
        </span>
      </div>
    </div>
  )
}
