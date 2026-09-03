import { useState, useCallback } from 'react'
import { uploadFormWithProgress } from '@/lib/api'

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

    try {
      const data = []
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)
        data.push(await uploadFormWithProgress('/files/upload', formData))
      }
      setFiles([])
      return data
    } finally {
      setUploading(false)
    }
  }, [files])

  return { files, uploading, addFiles, removeFile, uploadAll }
}
