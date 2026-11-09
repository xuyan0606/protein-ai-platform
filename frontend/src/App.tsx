import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatLayout } from '@/components/chat/ChatLayout'
import { AuthPage } from '@/pages/AuthPage'
import { HomePage } from '@/pages/HomePage'
import { ProjectListPage } from '@/pages/ProjectListPage'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import { BenchmarkListPage } from '@/pages/BenchmarkListPage'
import { BenchmarkCasePage } from '@/pages/BenchmarkCasePage'
import { PDBUploadPage } from '@/pages/PDBUploadPage'
import { WikiPage } from '@/pages/WikiPage'
import { AdminPage } from '@/pages/AdminPage'
import { TaskCenterPage } from '@/pages/TaskCenterPage'
import { ResearchEvidencePage } from '@/pages/ResearchEvidencePage'
import DataBrowser from '@/pages/DataBrowser'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ErrorBoundary } from '@/components/ErrorBoundary'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/platform/home" element={<HomePage />} />
      <Route path="/home" element={<Navigate to="/platform/home" replace />} />
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
      <Route path="/benchmarks" element={<BenchmarkListPage />} />
      <Route path="/benchmarks/:caseId" element={<BenchmarkCasePage />} />
      <Route
        path="/wiki/*"
        element={
          <ProtectedRoute>
            <WikiPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kb"
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
      <Route
        path="/tasks"
        element={
          <ProtectedRoute>
            <TaskCenterPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/research"
        element={
          <ProtectedRoute>
            <ResearchEvidencePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/platform/home" replace />} />
      <Route path="*" element={<Navigate to="/platform/home" replace />} />
    </Routes>
  )
}

export default App
