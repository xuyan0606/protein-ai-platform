import { useState, useEffect } from 'react'
import { Dna, FileText, Table2, Loader2 } from 'lucide-react'
import { ProteinViewer } from '@/components/viewer/ProteinViewer'

interface Props {
  fileName: string
  fileType: string
  content?: string
  fileUrl?: string
}

export function FileViewer({ fileName, fileType, content, fileUrl }: Props) {
  const [pdbContent, setPdbContent] = useState<string | null>(content || null)
  const [loading, setLoading] = useState(false)

  const isPDB = fileType.includes('pdb') || fileName.endsWith('.pdb') || fileName.endsWith('.cif')
  const isFasta = fileType.includes('fasta') || fileName.endsWith('.fasta') || fileName.endsWith('.fa')
  const isCSV = fileType.includes('csv') || fileName.endsWith('.csv')

  useEffect(() => {
    if (isPDB && !content && fileUrl) {
      setLoading(true)
      fetch(fileUrl)
        .then((r) => r.text())
        .then((text) => setPdbContent(text))
        .catch(() => setPdbContent(null))
        .finally(() => setLoading(false))
    }
  }, [isPDB, content, fileUrl])

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/50 border-b border-border">
        {isPDB ? (
          <Dna className="w-4 h-4 text-blue-500" />
        ) : isFasta ? (
          <FileText className="w-4 h-4 text-green-500" />
        ) : isCSV ? (
          <Table2 className="w-4 h-4 text-orange-500" />
        ) : (
          <FileText className="w-4 h-4 text-muted-foreground" />
        )}
        <span className="text-sm font-medium truncate">{fileName}</span>
        <span className="text-[10px] text-muted-foreground bg-secondary px-1.5 py-0.5 rounded ml-auto">
          {isPDB ? 'PDB' : isFasta ? 'FASTA' : isCSV ? 'CSV' : 'FILE'}
        </span>
      </div>

      {/* Content */}
      <div className="p-3">
        {isPDB ? (
          loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : pdbContent ? (
            <ProteinViewer pdbData={pdbContent} height={300} />
          ) : (
            <div className="bg-secondary rounded-lg p-8 text-center">
              <Dna className="w-12 h-12 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No structure data available</p>
            </div>
          )
        ) : isFasta ? (
          <pre className="text-xs font-mono bg-secondary rounded-lg p-3 overflow-x-auto max-h-60 overflow-y-auto">
            <code>{content || '>example_sequence\nMKAILVVLLYTFTLPANAS...'}</code>
          </pre>
        ) : (
          <div className="text-xs text-muted-foreground text-center py-4">
            {content ? (
              <pre className="text-left font-mono bg-secondary rounded-lg p-3 overflow-x-auto max-h-60">{content}</pre>
            ) : (
              'File preview not available for this format'
            )}
          </div>
        )}
      </div>
    </div>
  )
}
