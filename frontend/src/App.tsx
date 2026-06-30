import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatLayout } from '@/components/chat/ChatLayout'
import { AuthPage } from '@/pages/AuthPage'
import { HomePage } from '@/pages/HomePage'
import { ProjectListPage } from '@/pages/ProjectListPage'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import { PDBUploadPage } from '@/pages/PDBUploadPage'
import { WikiPage } from '@/pages/WikiPage'
import DataBrowser from '@/pages/DataBrowser'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ErrorBoundary } from '@/components/ErrorBoundary'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/home" element={<HomePage />} />
      <Route
        path="/chat/agent"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <ChatLayout />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <ProjectDetailPage />
          </ProtectedRoute>
        }
      />
      <Route path="/data" element={<DataBrowser />} />
      <Route
        path="/wiki"
        element={
          <ProtectedRoute>
            <WikiPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pdb"
        element={
          <ProtectedRoute>
            <PDBUploadPage />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  )
}

export default App
