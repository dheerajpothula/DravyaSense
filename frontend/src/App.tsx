import { Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <Routes>
      {/* Landing page — public-facing research site */}
      <Route path="/" element={<Landing />} />

      {/* Application workspace — all analysis modules live under /dashboard */}
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/dashboard/*" element={<Dashboard />} />
    </Routes>
  )
}

export default App
