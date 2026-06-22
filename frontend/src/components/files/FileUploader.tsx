import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, X, CheckCircle } from 'lucide-react'

interface UploadedFile {
  name: string
  size: number
  progress: number
  status: 'uploading' | 'done' | 'error'
}

interface Props {
  onFilesChange?: (files: File[]) => void
}

export function FileUploader({ onFilesChange }: Props) {
  const [uploaded, setUploaded] = useState<UploadedFile[]>([])

  const onDrop = useCallback(
    (accepted: File[]) => {
      const newFiles = accepted.map((f) => ({
        name: f.name,
        size: f.size,
        progress: 0,
        status: 'uploading' as const,
      }))
      setUploaded((prev) => [...prev, ...newFiles])

      // Simulate upload progress
      accepted.forEach((_, i) => {
        const idx = uploaded.length + i
        let progress = 0
        const interval = setInterval(() => {
          progress += Math.random() * 40
          if (progress >= 100) {
            progress = 100
            clearInterval(interval)
            setUploaded((prev) =>
              prev.map((f, j) =>
                j === idx ? { ...f, progress: 100, status: 'done' as const } : f
              )
            )
          } else {
            setUploaded((prev) =>
              prev.map((f, j) => (j === idx ? { ...f, progress } : f))
            )
          }
        }, 300)
      })

      onFilesChange?.(accepted)
    },
    [uploaded.length, onFilesChange]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'chemical/x-pdb': ['.pdb'],
      'text/x-fasta': ['.fasta', '.fa'],
      'chemical/x-cif': ['.cif'],
      'chemical/x-sdf': ['.sdf', '.mol'],
      'text/plain': ['.txt'],
      'text/csv': ['.csv'],
      'application/json': ['.json'],
    },
  })

  const removeFile = (index: number) => {
    setUploaded((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div>
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-muted-foreground/30'
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {isDragActive
            ? 'Drop files here...'
            : 'Drag & drop files, or click to browse'}
        </p>
        <p className="text-[11px] text-muted-foreground/60 mt-1">
          .pdb .fasta .cif .sdf .txt .csv .json
        </p>
      </div>

      {/* File list */}
      {uploaded.length > 0 && (
        <div className="mt-3 space-y-2">
          {uploaded.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-2 rounded-lg bg-secondary/50 text-sm"
            >
              <File className="w-4 h-4 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="truncate text-xs">{file.name}</span>
                  <span className="text-[10px] text-muted-foreground shrink-0 ml-2">
                    {formatSize(file.size)}
                  </span>
                </div>
                {file.status === 'uploading' && (
                  <div className="mt-1 w-full bg-secondary rounded-full h-1">
                    <div
                      className="bg-primary h-1 rounded-full transition-all duration-300"
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                )}
              </div>
              {file.status === 'done' ? (
                <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
              ) : (
                <button
                  onClick={() => removeFile(i)}
                  className="text-muted-foreground hover:text-foreground shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
