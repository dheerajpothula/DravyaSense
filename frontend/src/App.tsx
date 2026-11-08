import { Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import { DashboardHome } from './pages/Dashboard'
import DatasetsPage from './pages/datasets/DatasetsPage'

function App() {
  return (
    <Routes>
      {/* Public landing page */}
      <Route path="/" element={<Landing />} />

      {/* Application workspace — Dashboard is the layout shell */}
      <Route path="/dashboard" element={<Dashboard />}>
        {/* Default child — overview */}
        <Route index element={<DashboardHome />} />

        {/* Module routes */}
        <Route path="datasets" element={<DatasetsPage />} />

        {/* Future modules — add here as they are built */}
        {/* <Route path="explorer"   element={<DataExplorerPage />} /> */}
        {/* <Route path="preprocess" element={<PreprocessingPage />} /> */}
        {/* <Route path="pca"        element={<PCAPage />} /> */}
        {/* <Route path="tsne"       element={<TSNEPage />} /> */}
        {/* <Route path="compare"    element={<ComparePage />} /> */}
        {/* <Route path="evaluation" element={<EvaluationPage />} /> */}
        {/* <Route path="history"    element={<HistoryPage />} /> */}
        {/* <Route path="insights"   element={<InsightsPage />} /> */}
        {/* <Route path="settings"   element={<SettingsPage />} /> */}
      </Route>
    </Routes>
  )
}

export default App
