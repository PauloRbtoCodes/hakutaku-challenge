import React, { useState } from 'react'
import { api } from '../api/client'

export function ExtractModal({ onClose, onSuccess }) {
  const [documentText, setDocumentText] = useState('')
  const [sourceDoc, setSourceDoc]       = useState('')
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(null)
  const [result, setResult]             = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!documentText.trim() || !sourceDoc.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.extract(documentText, sourceDoc)
      setResult(data)
      onSuccess?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(26,26,46,0.4)',
      backdropFilter: 'blur(6px)',
      padding: 16,
    }}>
      <div style={{
        background: '#ffffff',
        border: '1px solid #EDE8E0',
        borderRadius: 18,
        boxShadow: '0 24px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 580,
        maxHeight: '90vh',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid #F0EBE3',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 9,
              background: '#FFF7ED',
              border: '1px solid #FED7AA',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16,
            }}>📄</div>
            <div>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#1A1A2E' }}>
                Processar Documento
              </p>
              <p style={{ margin: 0, fontSize: 11, color: '#9CA3AF' }}>
                Pipeline LLM em 3 etapas
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF', fontSize: 22, lineHeight: 1, padding: '4px 6px' }}>×</button>
        </div>

        {result ? (
          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 20 }}>✅</span>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#059669' }}>
                Documento processado com sucesso
              </p>
            </div>
            <div style={{ borderRadius: 10, background: '#F0FDF4', border: '1px solid #A7F3D0', padding: 14 }}>
              <p style={{ margin: '0 0 3px', fontSize: 12, color: '#6B7280' }}>
                Fonte: <span style={{ color: '#1A1A2E', fontWeight: 600 }}>{result.source_doc}</span>
              </p>
              <p style={{ margin: 0, fontSize: 12, color: '#6B7280' }}>
                Erros de parse:{' '}
                <span style={{ color: result.parse_errors > 0 ? '#D97706' : '#059669', fontWeight: 600 }}>
                  {result.parse_errors}
                </span>
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginTop: 12 }}>
                {Object.entries(result.counts).map(([k, v]) => (
                  <div key={k} style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '8px 4px', border: '1px solid #D1FAE5' }}>
                    <p style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#FF791F' }}>{v}</p>
                    <p style={{ margin: 0, fontSize: 10, color: '#9CA3AF' }}>{k}</p>
                  </div>
                ))}
              </div>
            </div>
            <button onClick={onClose} style={btnPrimary}>Fechar e atualizar grafo</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
            <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <Field label="Nome do documento / reunião">
                <input
                  type="text"
                  value={sourceDoc}
                  onChange={(e) => setSourceDoc(e.target.value)}
                  placeholder="ex: reuniao-sprint-2025-05-06"
                  style={inputStyle}
                />
              </Field>
              <Field label="Texto do documento">
                <textarea
                  value={documentText}
                  onChange={(e) => setDocumentText(e.target.value)}
                  placeholder="Cole aqui o texto da reunião, chat ou documento..."
                  rows={11}
                  style={{ ...inputStyle, resize: 'none', fontFamily: 'monospace', fontSize: 12 }}
                />
              </Field>
              {error && (
                <p style={{ margin: 0, fontSize: 12, color: '#DC2626', background: '#FEF2F2', padding: '8px 12px', borderRadius: 8, border: '1px solid #FECACA' }}>
                  {error}
                </p>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10, padding: '14px 20px', borderTop: '1px solid #F0EBE3', flexShrink: 0 }}>
              <button type="button" onClick={onClose} style={btnSecondary}>Cancelar</button>
              <button
                type="submit"
                disabled={loading || !documentText.trim() || !sourceDoc.trim()}
                style={{ ...btnPrimary, flex: 1, opacity: loading || !documentText.trim() || !sourceDoc.trim() ? 0.5 : 1, cursor: loading || !documentText.trim() || !sourceDoc.trim() ? 'not-allowed' : 'pointer' }}
              >
                {loading ? (
                  <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.8s linear infinite' }} />
                    Processando...
                  </span>
                ) : 'Extrair Entidades'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

const inputStyle = {
  background: '#FAFAFA',
  border: '1px solid #E5DDD4',
  borderRadius: 9,
  padding: '10px 12px',
  color: '#1A1A2E',
  fontSize: 13,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

const btnPrimary = {
  flex: 1,
  padding: '10px 16px',
  background: '#FF791F',
  border: 'none',
  borderRadius: 10,
  color: '#fff',
  fontSize: 13,
  fontWeight: 700,
  cursor: 'pointer',
  boxShadow: '0 4px 14px rgba(255,121,31,0.35)',
}

const btnSecondary = {
  flex: 1,
  padding: '10px 16px',
  background: '#F5F0E8',
  border: '1px solid #E5DDD4',
  borderRadius: 10,
  color: '#6B7280',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
}
