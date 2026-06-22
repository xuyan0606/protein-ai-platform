import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderKanban, Plus, Trash2, ChevronRight, Dna, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface ProjectItem {
  id: string
  name: string
  description?: string
  sequence_count: number
  created_at: string
  updated_at: string
}

export function ProjectListPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchProjects = async () => {
    try {
      setLoading(true)
      const data = await api.getProjects()
      setProjects(data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  useEffect(() => { fetchProjects() }, [])

  const handleCreate = async () => {
    if (!name.trim()) return
    setCreating(true)
    try {
      const proj = await api.createProject(name.trim(), desc.trim() || undefined)
      setShowCreate(false)
      setName('')
      setDesc('')
      navigate(`/projects/${proj.id}`)
    } catch { /* ignore */ } finally { setCreating(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteProject(id)
      setProjects((p) => p.filter((x) => x.id !== id))
    } catch { /* ignore */ }
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <FolderKanban className="w-6 h-6 text-primary" />
            <h1 className="text-xl font-bold">Projects</h1>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
          >
            <Plus className="w-4 h-4" />
            New Project
          </button>
        </div>

        {/* Create dialog */}
        {showCreate && (
          <>
            <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setShowCreate(false)} />
            <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
              <div className="bg-card border border-border rounded-2xl shadow-xl p-6 w-full max-w-md">
                <h2 className="font-semibold mb-4">New Project</h2>
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Project name (required)"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm mb-2 focus:outline-none focus:border-ring"
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
                <textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="Description (optional)"
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm mb-4 focus:outline-none focus:border-ring resize-none"
                />
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary">Cancel</button>
                  <button onClick={handleCreate} disabled={!name.trim() || creating} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-40 flex items-center gap-2">
                    {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Create
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Project list */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-16">
            <FolderKanban className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
            <p className="text-muted-foreground">No projects yet</p>
            <p className="text-sm text-muted-foreground/70 mt-1">Create a project to manage multiple protein sequences</p>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((proj) => (
              <div
                key={proj.id}
                className="group flex items-center gap-4 bg-card border border-border rounded-xl p-4 hover:border-ring/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/projects/${proj.id}`)}
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Dna className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm">{proj.name}</h3>
                  {proj.description && (
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{proj.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
                    <span>{proj.sequence_count} sequences</span>
                    <span>{new Date(proj.updated_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(proj.id) }}
                  className="p-2 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-all" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
