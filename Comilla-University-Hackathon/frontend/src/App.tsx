// Routes (SRS 3.3, 3.4): / start, /chat chat, /history past checklists, /admin dashboard (no phone needed).

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useSession } from './application/useSession'
import { OfflineBanner } from './presentation/components/OfflineBanner'
import { AdminPage } from './presentation/pages/AdminPage'
import { ChatPage } from './presentation/pages/ChatPage'
import { HistoryPage } from './presentation/pages/HistoryPage'
import { StartPage } from './presentation/pages/StartPage'

function App() {
  const session = useSession()

  return (
    <BrowserRouter>
      <OfflineBanner />
      <Routes>
        <Route path="/" element={<StartPage session={session} />} />
        <Route
          path="/chat"
          element={
            session.phone ? (
              <ChatPage session={session} phone={session.phone} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/history"
          element={session.phone ? <HistoryPage phone={session.phone} /> : <Navigate to="/" replace />}
        />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
