import React from 'react'

function Metric({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '5px 12px', gap: 1 }}>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || '#1A1A2E', lineHeight: 1 }}>
        {value ?? '—'}
      </span>
      <span style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 500, whiteSpace: 'nowrap', letterSpacing: '0.03em' }}>
        {label}
      </span>
    </div>
  )
}

function Sep() {
  return <div style={{ width: 1, height: 24, background: '#E5DDD4', flexShrink: 0, margin: '0 2px' }} />
}

export function MetricsBar({ context, nodeCount, edgeCount, proposalCount }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      background: '#ffffff',
      borderBottom: '1px solid #EDE8E0',
      padding: '0 8px',
      overflowX: 'auto',
      flexShrink: 0,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <Metric label="Docs"      value={context?.document_count ?? 0} color="#FF791F" />
      <Sep />
      <Metric label="Nodes"     value={nodeCount}                    color="#2563EB" />
      <Metric label="Edges"     value={edgeCount}                    color="#2563EB" />
      <Sep />
      <Metric label="Projetos"  value={context?.projects?.length}    color="#2563EB" />
      <Metric label="Pessoas"   value={context?.persons?.length}     color="#059669" />
      <Metric label="Tasks"     value={context?.tasks?.length}       color="#D97706" />
      <Metric label="Riscos"    value={context?.risks?.length}       color="#DC2626" />
      <Metric label="Decisões"  value={context?.decisions?.length}   color="#7C3AED" />
      <Metric label="Perguntas" value={context?.open_questions?.length} color="#EA580C" />
      <Sep />
      <Metric label="Proposals" value={proposalCount}                color="#FF791F" />
    </div>
  )
}
