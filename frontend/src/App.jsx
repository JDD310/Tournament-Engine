import { BrowserRouter, Route, Routes } from 'react-router-dom'
import CreateTournamentPage from './pages/CreateTournamentPage.jsx'
import ManageTournamentPage from './pages/ManageTournamentPage.jsx'
import TournamentPage from './pages/TournamentPage.jsx'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<CreateTournamentPage />} />
      <Route path="/t/:id" element={<TournamentPage />} />
      <Route path="/t/:id/manage" element={<ManageTournamentPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
