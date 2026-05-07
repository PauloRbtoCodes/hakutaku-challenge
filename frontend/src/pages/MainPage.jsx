import React, { useState, useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useGraph }      from '../hooks/useGraph'
import { useProposals }  from '../hooks/useProposals'
import { useOrgContext } from '../hooks/useOrgContext'
import { MetricsBar }    from '../components/MetricsBar'
import { ProposalCard }  from '../components/ProposalCard'
import { GraphLegend }   from '../components/GraphLegend'
import { ExtractModal }  from '../components/ExtractModal'
import { ENTITY_CONFIG } from '../components/entityConfig'
import {
  ProjectNode, PersonNode, TaskNode,
  RiskNode, DecisionNode, OpenquestionNode,
} from '../components/EntityNode'

const NODE_TYPES = {
  project: ProjectNode, person: PersonNode, task: TaskNode,
  risk: RiskNode, decision: DecisionNode, openquestion: OpenquestionNode,
}

const NODE_COLORS = Object.fromEntries(
  Object.entries(ENTITY_CONFIG).map(([k, v]) => [k, v.color])
)

export function MainPage() {
  const { nodes: rawNodes, edges: rawEdges, loading: graphLoading, error: graphError, refresh: refreshGraph } = useGraph()
  const { proposals, loading: proposalsLoading, refresh: refreshProposals } = useProposals()
  const { context, refresh: refreshContext } = useOrgContext()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [sidebarTab,  setSidebarTab]  = useState('proposals')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showModal,   setShowModal]   = useState(false)
  const [selected,    setSelected]    = useState(null)

  useEffect(() => {
    setNodes(rawNodes)
    setEdges(rawEdges)
  }, [rawNodes, rawEdges, setNodes, setEdges])

  const handleExtractSuccess = useCallback(() => {
    refreshGraph()
    refreshProposals()
    refreshContext()
  }, [refreshGraph, refreshProposals, refreshContext])

  const urgentCount = proposals.filter(
    (p) => p.priority === 'critical' || p.priority === 'high'
  ).length

  const isEmpty = !graphLoading && !graphError && nodes.length === 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#FAF7F2', overflow: 'hidden' }}>

      {/* ── Top bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', height: 54, flexShrink: 0,
        background: '#ffffff',
        borderBottom: '1px solid #EDE8E0',
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: '#FFF7ED', border: '1px solid #FED7AA',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 4, flexShrink: 0,
            boxShadow: '0 2px 8px rgba(255,121,31,0.15)',
          }}>
            <img src="/hakutaku-mark.svg" alt="Hakutaku" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <div>
            <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: '#1A1A2E', letterSpacing: '-0.02em' }}>
              Hakutaku
            </p>
            <p style={{ margin: 0, fontSize: 9, color: '#9CA3AF', fontWeight: 500, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
              Knowledge Graph
            </p>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {urgentCount > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 11px', borderRadius: 99,
              background: '#FEF2F2', border: '1px solid #FECACA',
              fontSize: 11, fontWeight: 600, color: '#DC2626',
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#DC2626', display: 'inline-block' }} />
              {urgentCount} urgente{urgentCount > 1 ? 's' : ''}
            </div>
          )}
          <button
            onClick={() => setShowModal(true)}
            style={{
              padding: '7px 16px',
              background: '#FF791F', border: 'none', borderRadius: 9,
              color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(255,121,31,0.3)',
              letterSpacing: '0.01em',
            }}
          >
            + Processar Doc
          </button>
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            style={{
              padding: '7px 11px',
              background: '#F5F0E8', border: '1px solid #E5DDD4', borderRadius: 9,
              color: '#6B7280', fontSize: 14, fontWeight: 700, cursor: 'pointer', lineHeight: 1,
            }}
          >
            {sidebarOpen ? '›' : '‹'}
          </button>
        </div>
      </div>

      {/* ── Metrics ── */}
      <MetricsBar
        context={context}
        nodeCount={nodes.length}
        edgeCount={edges.length}
        proposalCount={proposals.length}
      />

      {/* ── Body ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Graph canvas ── */}
        <div style={{ flex: 1, position: 'relative' }}>

          {/* Loading */}
          {graphLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(250,247,242,0.85)', zIndex: 10 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ width: 36, height: 36, border: '3px solid #FED7AA', borderTopColor: '#FF791F', borderRadius: '50%', animation: 'spin 0.9s linear infinite', margin: '0 auto 12px' }} />
                <p style={{ margin: 0, color: '#9CA3AF', fontSize: 13 }}>Carregando grafo...</p>
              </div>
            </div>
          )}

          {/* Error */}
          {graphError && !graphLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10, padding: 24 }}>
              <div style={{ background: '#fff', border: '1px solid #FECACA', borderRadius: 16, padding: 28, maxWidth: 360, textAlign: 'center', boxShadow: '0 8px 30px rgba(0,0,0,0.1)' }}>
                <span style={{ fontSize: 36 }}>⚠️</span>
                <p style={{ margin: '10px 0 4px', fontSize: 15, fontWeight: 700, color: '#DC2626' }}>Erro ao carregar grafo</p>
                <p style={{ margin: '0 0 4px', fontSize: 12, color: '#6B7280' }}>{graphError}</p>
                <p style={{ margin: '0 0 18px', fontSize: 11, color: '#9CA3AF' }}>Verifique se o backend está rodando em localhost:8000</p>
                <button onClick={refreshGraph} style={{ padding: '8px 22px', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, color: '#DC2626', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                  Tentar novamente
                </button>
              </div>
            </div>
          )}

          {/* ── Empty state with Sage GIF ── */}
          {isEmpty && (
            <div style={{
              position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              zIndex: 5, pointerEvents: 'none',
              gap: 0,
            }}>
              <img
                src="/hakutaku-sage.gif"
                alt="Hakutaku Sage"
                className="sage-float"
                style={{ width: 220, height: 'auto', userSelect: 'none' }}
              />
              <p style={{ margin: '4px 0 6px', fontSize: 20, fontWeight: 800, color: '#1A1A2E', letterSpacing: '-0.03em', textAlign: 'center' }}>
                O segundo cérebro<br />
                <span style={{ color: '#FF791F' }}>da sua empresa</span>
              </p>
              <p style={{ margin: 0, fontSize: 13, color: '#9CA3AF', textAlign: 'center', maxWidth: 280 }}>
                Processe um documento para construir<br />o grafo de conhecimento organizacional.
              </p>
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            onNodeClick={(_, node) => setSelected(node)}
            onPaneClick={() => setSelected(null)}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            colorMode="light"
            minZoom={0.15}
            maxZoom={2.5}
          >
            <Background
              variant={BackgroundVariant.Dots}
              color="rgba(255,121,31,0.18)"
              gap={28}
              size={1.5}
            />
            <Controls style={{ background: '#fff', border: '1px solid #EDE8E0', borderRadius: 10 }} />
            <MiniMap
              nodeColor={(n) => NODE_COLORS[n.type] || '#D1D5DB'}
              maskColor="rgba(245,240,232,0.75)"
              style={{ background: '#fff', border: '1px solid #EDE8E0', borderRadius: 10 }}
            />
          </ReactFlow>

          {/* Selected node panel */}
          {selected && (
            <div style={{
              position: 'absolute', bottom: 16, left: 16, width: 240,
              background: '#ffffff', border: `1px solid ${(ENTITY_CONFIG[selected.type] || ENTITY_CONFIG.project).border}`,
              borderRadius: 14, padding: 14,
              boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
              zIndex: 10,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#1A1A2E', lineHeight: 1.3 }}>
                  {selected.data.label}
                </p>
                <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: '#9CA3AF', fontSize: 17, cursor: 'pointer', padding: '0 0 0 8px', flexShrink: 0 }}>×</button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Row k="tipo" v={selected.type} color={(ENTITY_CONFIG[selected.type] || ENTITY_CONFIG.project).color} />
                {Object.entries(selected.data)
                  .filter(([k, v]) => k !== 'label' && v !== null && v !== undefined)
                  .map(([k, v]) => <Row key={k} k={k} v={String(v)} />)}
              </div>
            </div>
          )}
        </div>

        {/* ── Sidebar ── */}
        {sidebarOpen && (
          <div style={{
            width: 300,
            background: '#ffffff',
            borderLeft: '1px solid #EDE8E0',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
            flexShrink: 0,
          }}>
            {/* Sage mascot header */}
            <div style={{
              padding: '14px 16px 10px',
              borderBottom: '1px solid #F0EBE3',
              background: 'linear-gradient(180deg, #FFF7ED 0%, #ffffff 100%)',
              display: 'flex', alignItems: 'center', gap: 12,
              flexShrink: 0,
            }}>
              <img
                src="/hakutaku-sage.gif"
                alt="Sage"
                style={{ width: 52, height: 52, objectFit: 'contain', flexShrink: 0 }}
              />
              <div>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#1A1A2E' }}>
                  {proposals.length === 0
                    ? 'Tudo em ordem!'
                    : `${proposals.length} recomendação${proposals.length > 1 ? 'ões' : ''}`}
                </p>
                <p style={{ margin: '2px 0 0', fontSize: 11, color: '#9CA3AF' }}>
                  {proposals.length === 0
                    ? 'Nenhum alerta detectado.'
                    : urgentCount > 0
                      ? `${urgentCount} urgente${urgentCount > 1 ? 's' : ''} · ação necessária`
                      : 'Atenção moderada recomendada'}
                </p>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid #EDE8E0', flexShrink: 0 }}>
              {[
                { key: 'proposals', label: `Proposals${proposals.length > 0 ? ` (${proposals.length})` : ''}` },
                { key: 'legend',    label: 'Legenda' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setSidebarTab(tab.key)}
                  style={{
                    flex: 1, padding: '10px 8px',
                    background: 'none', border: 'none',
                    borderBottom: sidebarTab === tab.key ? '2px solid #FF791F' : '2px solid transparent',
                    color: sidebarTab === tab.key ? '#FF791F' : '#9CA3AF',
                    fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    transition: 'color 0.15s',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {sidebarTab === 'proposals' && (
                <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {proposalsLoading ? (
                    <p style={{ textAlign: 'center', color: '#9CA3AF', fontSize: 13, padding: '32px 0' }}>Carregando...</p>
                  ) : proposals.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '24px 16px' }}>
                      <p style={{ margin: 0, fontSize: 12, color: '#9CA3AF' }}>Nenhum proposal gerado ainda.</p>
                    </div>
                  ) : (
                    proposals.map((p, i) => <ProposalCard key={i} proposal={p} />)
                  )}
                </div>
              )}
              {sidebarTab === 'legend' && <GraphLegend />}
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <ExtractModal
          onClose={() => setShowModal(false)}
          onSuccess={() => { setShowModal(false); handleExtractSuccess() }}
        />
      )}
    </div>
  )
}

function Row({ k, v, color }) {
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
      <span style={{ fontSize: 10, color: '#9CA3AF', flexShrink: 0 }}>{k}:</span>
      <span style={{ fontSize: 11, color: color || '#6B7280', fontWeight: 500, wordBreak: 'break-word' }}>{v}</span>
    </div>
  )
}
