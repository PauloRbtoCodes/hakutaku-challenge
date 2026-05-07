import React from 'react'
import { ReactFlowProvider } from '@xyflow/react'
import { MainPage } from './pages/MainPage'

export default function App() {
  return (
    <ReactFlowProvider>
      <MainPage />
    </ReactFlowProvider>
  )
}
