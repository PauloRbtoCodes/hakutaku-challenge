const BASE = 'http://localhost:8000'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `POST ${path} → ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => get('/health'),
  graph: () => get('/graph'),
  proposals: () => get('/proposals'),
  context: () => get('/context'),
  extract: (document_text, source_doc) =>
    post('/extract', { document_text, source_doc }),
}
