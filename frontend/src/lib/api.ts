const BASE = '/api'

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  // 204 No Content — nothing to parse
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string; user: { id: number; email: string; name: string } }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) }
    ),

  register: (email: string, password: string, name: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string; user: { id: number; email: string; name: string } }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, name }) }
    ),

  // Conversations
  getConversations: () => request<any[]>('/conversations'),

  createConversation: () =>
    request<any>('/conversations', { method: 'POST', body: JSON.stringify({ title: 'New Conversation' }) }),

  getConversation: (id: string) => request<any>(`/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: 'DELETE' }),

  // Models
  getModels: () => request<Array<{ id: string; name: string; provider: string; model: string; description: string; available: boolean }>>('/chat/models'),

  // Tools
  getTools: () => request<{ tools: any[]; categories: Record<string, string[]> }>('/tools'),

  callTool: (name: string, params: Record<string, unknown>) =>
    request<any>(`/tools/${name}/call`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  // Auth (extended)
  getMe: () =>
    request<{ id: string; email: string; name: string }>('/auth/me'),

  refreshToken: (refresh_token: string) =>
    request<{ access_token: string; refresh_token: string }>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token }),
    }),

  // Projects
  getProjects: () => request<any[]>('/projects'),

  createProject: (name: string, description?: string) =>
    request<any>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),

  getProject: (id: string) => request<any>(`/projects/${id}`),

  updateProject: (id: string, data: { name?: string; description?: string }) =>
    request<any>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),

  addSequence: (projectId: string, name: string, sequence: string, notes?: string) =>
    request<any>(`/projects/${projectId}/sequences`, {
      method: 'POST',
      body: JSON.stringify({ name, sequence, notes }),
    }),

  removeSequence: (projectId: string, seqId: string) =>
    request<void>(`/projects/${projectId}/sequences/${seqId}`, { method: 'DELETE' }),

  batchRun: (projectId: string, tool: string, params?: Record<string, unknown>) =>
    request<any>(`/projects/${projectId}/batch-run`, {
      method: 'POST',
      body: JSON.stringify({ tool, params: params || {} }),
    }),

  getBatchJobs: (projectId: string) => request<any[]>(`/projects/${projectId}/batch-jobs`),

  // Files
  getFiles: () => request<any[]>('/files'),

  uploadFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('token')
    return fetch(`${BASE}/files/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    })
  },

  // ========== Data Browser ==========
  getDataStats: () => request<any>('/data/stats'),

  searchData: (q: string, category?: string, limit = 20) => {
    const params = new URLSearchParams({ q, limit: String(limit) })
    if (category) params.set('category', category)
    return request<any>(`/data/search?${params}`)
  },

  getProtein: (uniprotId: string) => request<any>(`/data/protein/${uniprotId}`),

  getProteinKinetics: (uniprotId: string, paramType?: string) => {
    const params = paramType ? `?param_type=${paramType}` : ''
    return request<any>(`/data/protein/${uniprotId}/kinetics${params}`)
  },

  getProteinStability: (uniprotId: string) =>
    request<any>(`/data/protein/${uniprotId}/stability`),

  getProteinStructures: (uniprotId: string) =>
    request<any>(`/data/protein/${uniprotId}/structures`),

  getProteinEvolution: (uniprotId: string) =>
    request<any>(`/data/protein/${uniprotId}/evolution`),

  getECNumber: (ec: string) => request<any>(`/data/ec/${ec}`),

  searchSubstrate: (query: string) => request<any>(`/data/substrate/${query}`),

  getReaction: (rheaId: number) => request<any>(`/data/reaction/${rheaId}`),

  triggerIngestion: (source: string, force = false) =>
    request<any>(`/data/ingest/${source}?force=${force}`, { method: 'POST' }),

  // Publish — Wiki + knowledge base
  publishReport: (projectId: string, data: {
    title: string; content: string; conversation_id?: number; tags?: string[]
  }) => request<{
    file_id: string; filename: string; outline_doc_id: string | null; wiki_url: string | null
  }>(`/projects/${projectId}/publish`, { method: 'POST', body: JSON.stringify(data) }),

  generateReport: (projectId: string, conversationId: number) =>
    request<{ title: string; content: string; conversation_id: number }>(
      `/projects/${projectId}/generate-report`,
      { method: 'POST', body: JSON.stringify({ conversation_id: conversationId }) }
    ),

  getProjectFiles: (projectId: string, fileType?: string) => {
    const params = fileType ? `?file_type=${fileType}` : ''
    return request<any[]>(`/projects/${projectId}/files${params}`)
  },

  deleteProjectFile: (projectId: string, fileId: string) =>
    request<{ ok: boolean }>(`/projects/${projectId}/files/${fileId}`, { method: 'DELETE' }),

  bindConversationToProject: (conversationId: number, projectId: string | null) =>
    request<{ ok: boolean }>(`/conversations/${conversationId}/project`, {
      method: 'PATCH', body: JSON.stringify({ project_id: projectId })
    }),

  getProjectConversations: (projectId: string) =>
    request<any[]>(`/projects/${projectId}/conversations`),

  // Wiki tree + pages
  getWikiTree: (projectId: string) =>
    request<{ collection_id: string | null; root_doc_id: string | null; documents: Array<{
      id: string; title: string; parent_id: string | null; url_id: string | null;
      updated_at: string | null; emoji: string | null
    }> }>(`/projects/${projectId}/wiki/tree`),

  getWikiPage: (projectId: string, docId: string) =>
    request<{ id: string; title: string; text: string; updated_at: string | null; url_id: string | null }>(
      `/projects/${projectId}/wiki/pages/${docId}`
    ),

  downloadProjectFile: (projectId: string, fileId: string) => {
    const token = localStorage.getItem('token')
    return fetch(`${BASE}/projects/${projectId}/files/${fileId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },

  getFileContent: (projectId: string, fileId: string) => {
    const token = localStorage.getItem('token')
    return fetch(`${BASE}/projects/${projectId}/files/${fileId}/content`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(r => r.text())
  },
}
