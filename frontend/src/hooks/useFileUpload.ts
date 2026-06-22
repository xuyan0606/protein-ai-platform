import { useState, useCallback } from 'react'

export function useFileUpload() {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)

  const addFiles = useCallback((newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles])
  }, [])

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const uploadAll = useCallback(async () => {
    setUploading(true)
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      const data = await res.json()
      setFiles([])
      return data
    } finally {
      setUploading(false)
    }
  }, [files])

  return { files, uploading, addFiles, removeFile, uploadAll }
}
