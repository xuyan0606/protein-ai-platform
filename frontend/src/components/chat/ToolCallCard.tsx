import { useState, useMemo } from 'react'
import type { ToolCall } from '@/stores/chat'
import { Loader2, CheckCircle2, XCircle, Clock, Dna, ChevronDown, ChevronUp } from 'lucide-react'
import { ProteinViewer } from '@/components/viewer/ProteinViewer'
import { BenchmarkReport, isBenchmarkResult } from '@/components/analysis/BenchmarkReport'
import { MutationScoreCard, isMutationScoreResult } from '@/components/analysis/MutationScoreCard'
import { BlastResultView, isBlastResult } from '@/components/analysis/BlastResultView'
import { MDResultView, isMDResult } from '@/components/analysis/MDResultView'
import { ESM2ResultCard, isESM2Result } from '@/components/analysis/ESM2ResultCard'
import { ECPredictionCard, isECPredictionResult } from '@/components/analysis/ECPredictionCard'
import { CatalyticParamsCard, isCatalyticParamsResult } from '@/components/analysis/CatalyticParamsCard'

interface Props {
  toolCall: ToolCall
}

const FOLDING_TOOLS = ['esmfold_folding', 'alphafold_folding', 'alphafold2_folding', 'rosettafold_folding']

function extractPdbData(resultPreview: string): string | null {
  if (resultPreview.includes('ATOM') || resultPreview.includes('HEADER')) return resultPreview
  try {
    const obj = JSON.parse(resultPreview)
    const pdb = obj.pdb || obj.pdb_content || obj.pdb_data || obj.structure
    if (typeof pdb === 'string' && (pdb.includes('ATOM') || pdb.includes('HEADER'))) return pdb
  } catch { /* not JSON, try Python repr */ }
  try {
    const json = resultPreview
      .replace(/'/g, '"')
      .replace(/\bNone\b/g, 'null')
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
    const obj = JSON.parse(json)
    const pdb = obj.pdb || obj.pdb_content || obj.pdb_data || obj.structure
    if (typeof pdb === 'string' && (pdb.includes('ATOM') || pdb.includes('HEADER'))) return pdb
  } catch { /* not parseable */ }
  return null
}

function tryParseResult(preview: string | undefined): unknown | null {
  if (!preview) return null
  // New format: proper JSON from json.dumps
  try {
    return JSON.parse(preview)
  } catch { /* fall through to Python repr parser */ }
  // Old format: Python repr → convert to valid JSON
  try {
    const json = preview
      .replace(/'/g, '"')
      .replace(/\bNone\b/g, 'null')
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
    return JSON.parse(json)
  } catch {
    return null
  }
}

const ANALYSIS_TOOLS = ['protein_benchmark', 'mutation_priority_score', 'blast_search', 'gromacs_md', 'esm2_predict', 'protssn_score', 'enzyme_function', 'kcat_predict']

export function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false)
  const statusIcon = {
    pending: <Clock className="w-4 h-4 text-muted-foreground" />,
    running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
    completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
    failed: <XCircle className="w-4 h-4 text-red-500" />,
  }

  const isFolding = FOLDING_TOOLS.includes(toolCall.name)
  const pdbData = toolCall.resultPreview ? extractPdbData(toolCall.resultPreview) : null
  const hasStructure = isFolding && toolCall.status === 'completed' && pdbData

  // Parse result for analysis tools
  const analysisResult = useMemo(() => {
    if (!ANALYSIS_TOOLS.includes(toolCall.name) || toolCall.status !== 'completed') return null
    return tryParseResult(toolCall.resultPreview)
  }, [toolCall.name, toolCall.status, toolCall.resultPreview])

  const analysisView = useMemo(() => {
    if (!analysisResult) return null
    if (toolCall.name === 'protein_benchmark' && isBenchmarkResult(analysisResult)) {
      return <BenchmarkReport data={analysisResult} />
    }
    if (toolCall.name === 'mutation_priority_score' && isMutationScoreResult(analysisResult)) {
      return <MutationScoreCard data={analysisResult} />
    }
    if (toolCall.name === 'blast_search' && isBlastResult(analysisResult)) {
      return <BlastResultView data={analysisResult} />
    }
    if (toolCall.name === 'gromacs_md' && isMDResult(analysisResult)) {
      return <MDResultView data={analysisResult} />
    }
    if ((toolCall.name === 'esm2_predict' || toolCall.name === 'protssn_score') && isESM2Result(analysisResult)) {
      return <ESM2ResultCard data={analysisResult} />
    }
    if (toolCall.name === 'enzyme_function' && isECPredictionResult(analysisResult)) {
      return <ECPredictionCard data={analysisResult} />
    }
    if (toolCall.name === 'kcat_predict' && isCatalyticParamsResult(analysisResult)) {
      return <CatalyticParamsCard data={analysisResult} />
    }
    return null
  }, [analysisResult, toolCall.name])

  const hasAnalysisView = analysisView !== null
  const hasExpandable = hasStructure || hasAnalysisView

  return (
    <div className="border border-border rounded-lg bg-secondary/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-3 text-left hover:bg-secondary/20 transition-colors"
      >
        {statusIcon[toolCall.status]}
        <span className="text-xs font-medium flex items-center gap-1.5">
          {toolCall.name}
          {hasStructure && <Dna className="w-3 h-3 text-blue-400" />}
        </span>
        {toolCall.duration && (
          <span className="text-[10px] text-muted-foreground">
            {toolCall.duration}s
          </span>
        )}
        <div className="flex-1" />
        {hasExpandable && (
          expanded ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />
        )}
      </button>

      {toolCall.status === 'running' && (
        <div className="px-3 pb-2">
          <div className="w-full bg-secondary rounded-full h-1 overflow-hidden">
            <div className="bg-blue-500 h-1 rounded-full animate-pulse w-2/3" />
          </div>
        </div>
      )}

      {toolCall.error && (
        <p className="px-3 pb-2 text-xs text-red-500">{toolCall.error}</p>
      )}

      {expanded && hasStructure && (
        <div className="px-3 pb-3">
          <ProteinViewer pdbData={pdbData!} height={250} />
        </div>
      )}

      {expanded && hasAnalysisView && !hasStructure && (
        <div className="px-3 pb-3">
          {analysisView}
        </div>
      )}
    </div>
  )
}
