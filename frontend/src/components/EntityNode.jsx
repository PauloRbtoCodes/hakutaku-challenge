import React from 'react'
import { Handle, Position } from '@xyflow/react'
import { ENTITY_CONFIG, STATUS_COLORS } from './entityConfig'

function StatusPill({ status }) {
  const color = STATUS_COLORS[status] || '#9CA3AF'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
      textTransform: 'uppercase',
      padding: '2px 7px', borderRadius: 99,
      background: `${color}18`,
      color,
      border: `1px solid ${color}35`,
    }}>
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {status}
    </span>
  )
}

function MetaRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'baseline' }}>
      <span style={{ fontSize: 10, color: '#9CA3AF', flexShrink: 0 }}>{label}:</span>
      <span style={{ fontSize: 11, color: color || '#6B7280', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function EntityNode({ data, type }) {
  const cfg = ENTITY_CONFIG[type] || ENTITY_CONFIG.project
  return (
    <div style={{
      minWidth: 190, maxWidth: 230,
      borderRadius: 12,
      background: '#ffffff',
      border: `1px solid ${cfg.border}`,
      boxShadow: '0 2px 12px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.05)',
      overflow: 'hidden',
    }}>
      <Handle type="target" position={Position.Top}
        style={{ background: cfg.color, width: 6, height: 6, border: 'none' }} />

      {/* Header */}
      <div style={{
        padding: '7px 11px',
        background: cfg.light,
        borderBottom: `1px solid ${cfg.border}`,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span style={{ fontSize: 12 }}>{cfg.icon}</span>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.07em',
          textTransform: 'uppercase', color: cfg.color,
        }}>{cfg.label}</span>
      </div>

      {/* Body */}
      <div style={{ padding: '9px 11px', display: 'flex', flexDirection: 'column', gap: 5 }}>
        <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: '#1A1A2E', lineHeight: 1.35 }}>
          {data.label}
        </p>
        {data.status && <StatusPill status={data.status} />}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 1 }}>
          {data.severity !== undefined && (
            <MetaRow label="Severidade" value={`${data.severity}/10`}
              color={data.severity >= 7 ? '#DC2626' : '#D97706'} />
          )}
          {data.priority && <MetaRow label="Prioridade" value={data.priority} color="#D97706" />}
          {data.deadline && <MetaRow label="Prazo" value={data.deadline} color="#EA580C" />}
          {data.role && <MetaRow label="Papel" value={data.role} />}
          {data.decided_by && <MetaRow label="Por" value={data.decided_by} />}
          {data.asked_by && <MetaRow label="Por" value={data.asked_by} />}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom}
        style={{ background: cfg.color, width: 6, height: 6, border: 'none' }} />
    </div>
  )
}

export const ProjectNode      = (p) => <EntityNode {...p} type="project"      />
export const PersonNode       = (p) => <EntityNode {...p} type="person"       />
export const TaskNode         = (p) => <EntityNode {...p} type="task"         />
export const RiskNode         = (p) => <EntityNode {...p} type="risk"         />
export const DecisionNode     = (p) => <EntityNode {...p} type="decision"     />
export const OpenquestionNode = (p) => <EntityNode {...p} type="openquestion" />
