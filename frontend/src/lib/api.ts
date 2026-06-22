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
  getTools: () => request<any[]>('/tools'),

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
}
