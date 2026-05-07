import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

const TYPE_ORDER = ['project', 'person', 'task', 'risk', 'decision', 'openquestion']
const ROW_HEIGHT = 200
const COL_WIDTH = 280

function layoutNodes(rawNodes) {
  const byType = {}
  for (const t of TYPE_ORDER) byType[t] = []
  for (const node of rawNodes) {
    const bucket = TYPE_ORDER.includes(node.type) ? node.type : 'project'
    byType[bucket].push(node)
  }

  const positioned = []
  TYPE_ORDER.forEach((type, rowIdx) => {
    byType[type].forEach((node, colIdx) => {
      positioned.push({
        ...node,
        position: {
          x: colIdx * COL_WIDTH + 40,
          y: rowIdx * ROW_HEIGHT + 40,
        },
      })
    })
  })
  return positioned
}

function styleEdges(rawEdges) {
  return rawEdges.map((e) => ({
    ...e,
    style: { stroke: '#4b5563' },
    labelStyle: { fill: '#9ca3af', fontSize: 10 },
    labelBgStyle: { fill: '#1f2937', fillOpacity: 0.85 },
    labelBgPadding: [4, 2],
  }))
}

export function useGraph() {
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.graph()
      setNodes(layoutNodes(data.nodes))
      setEdges(styleEdges(data.edges))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { nodes, edges, loading, error, refresh: load }
}
