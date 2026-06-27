import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Dna, Upload, File, CheckCircle, AlertCircle, Loader2, ArrowRight, ChevronLeft } from 'lucide-react'
import { PDBAnalysisCard } from '@/components/analysis/PDBAnalysisCard'

interface AnalysisResult {
  header?: { title?: string }
  chains: any[]
  resolution?: number | null
  r_factor?: number | null
  space_group?: string | null
  unit_cell?: Record<string, number> | null
  b_factor_stats?: { mean: number; min: number; max: number } | null
  total_atoms: number
  total_residues: number
  method?: string | null
  deposited_date?: string | null
  object_name?: string
  download_url?: string
  file_name?: string
  file_size?: number
}

export function PDBUploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [pdbContent, setPdbContent] = useState<string | null>(null)

  const uploadAndAnalyze = async (f: File) => {
    setFile(f)
    setUploading(true)
    setError(null)
    setAnalysis(null)
    setPdbContent(null)

    const token = localStorage.getItem('token')
    const formData = new FormData()
    formData.append('file', f)

    try {
      // Upload
      const uploadResult = await new Promise<{ object_name: string; download_url: string }>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/files/upload')
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100))
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText))
          } else {
            reject(new Error('Upload failed'))
          }
        }
        xhr.onerror = () => reject(new Error('Network error'))
        xhr.send(formData)
      })

      setUploadProgress(100)

      // Analyze
      const resp = await fetch('/api/pdb/analyze-by-name', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ object_name: uploadResult.object_name }),
      })

      if (!resp.ok) throw new Error('Analysis failed')

      const data = await resp.json()
      setAnalysis({ ...data, object_name: uploadResult.object_name, download_url: uploadResult.download_url, file_name: f.name, file_size: f.size })

      // Fetch PDB content for 3D viewer
      try {
        const pdbResp = await fetch(uploadResult.download_url)
        if (pdbResp.ok) setPdbContent(await pdbResp.text())
      } catch { /* non-critical */ }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) uploadAndAnalyze(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'chemical/x-pdb': ['.pdb', '.ent'], 'chemical/x-cif': ['.cif'] },
    maxFiles: 1,
  })

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => navigate('/chat/agent')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Chat
          </button>
          <div className="flex-1" />
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Dna className="w-6 h-6 text-blue-500" />
            PDB Structure Analysis
          </h1>
        </div>

        {/* Drop zone */}
        {!analysis && (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all ${
              isDragActive
                ? 'border-primary bg-primary/5 scale-[1.01]'
                : 'border-border hover:border-muted-foreground/30 hover:bg-secondary/30'
            }`}
          >
            <input {...getInputProps()} />
            {uploading ? (
              <div className="space-y-4">
                <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary" />
                <div>
                  <p className="text-sm font-medium">{file?.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">Uploading & analyzing...</p>
                </div>
                <div className="w-64 mx-auto bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : (
              <>
                <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-base font-medium mb-2">
                  Drop a PDB or CIF file here
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse — .pdb .ent .cif
                </p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 flex items-center gap-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Analysis Result */}
        {analysis && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle className="w-4 h-4" />
                Analysis complete
              </div>
              <button
                onClick={() => { setFile(null); setAnalysis(null); setPdbContent(null); setError(null) }}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Analyze another
              </button>
            </div>

            <PDBAnalysisCard data={analysis} pdbContent={pdbContent ?? undefined} />

            {/* Quick actions */}
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/chat/agent', {
                  state: {
                    initialPrompt: `分析这个PDB结构 ${analysis.file_name || ''}，帮我分析其结构特征、稳定性、潜在的突变改造方案`,
                    uploadFile: file,
                  },
                })}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <ArrowRight className="w-4 h-4" />
                Deep Analysis in Chat
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}