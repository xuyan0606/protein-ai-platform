import { ArrowRight, RadioTower, ShieldCheck, ShieldX } from 'lucide-react'
import {
  ReportBadge,
  ReportBody,
  ReportHeader,
  ReportMetricCard,
  ReportMetricGrid,
  ReportPanel,
  ReportSection,
  ReportShell,
} from '@/components/analysis/ReportShell'

interface SignalPeptideRegion {
  start: number
  end: number | null
  positive_residues?: number
  hydrophobic_ratio?: number
}

export interface SignalPeptideData {
  found: boolean
  error?: string
  query?: {
    uniprot_id?: string | null
    sequence_length?: number
  }
  has_signal_peptide: boolean
  confidence: number
  predicted_type: string
  cleavage_site: string | null
  regions: {
    n_region: SignalPeptideRegion
    h_region: SignalPeptideRegion
    c_region: SignalPeptideRegion
  }
  model: string
  note?: string
  cache?: {
    hit: boolean
    source: string
  }
}

function formatRegion(name: string, region: SignalPeptideRegion) {
  const range = `${region.start}-${region.end ?? '?'}`
  if (name === 'n_region') return `${range} · 正电残基 ${region.positive_residues ?? 0}`
  if (name === 'h_region') return `${range} · 疏水比 ${(region.hydrophobic_ratio ?? 0).toFixed(2)}`
  return range
}

export function SignalPeptideCard({ data }: { data: SignalPeptideData }) {
  return (
    <ReportShell>
      <ReportHeader
        icon={RadioTower}
        title="信号肽预测"
        subtitle={`${data.query?.sequence_length ?? '-'} aa · ${data.model}`}
        badge={
          <ReportBadge tone={data.has_signal_peptide ? 'success' : 'neutral'}>
            {data.has_signal_peptide ? 'Detected' : 'Not Detected'}
          </ReportBadge>
        }
      />
      <ReportBody>
        {data.error ? (
          <ReportPanel tone="danger" className="text-xs text-red-700 dark:text-red-300">
            {data.error}
          </ReportPanel>
        ) : null}

        <ReportSection title="Summary">
          <ReportMetricGrid>
            <ReportMetricCard
              label="预测结果"
              value={data.has_signal_peptide ? '存在' : '未检出'}
              tone={data.has_signal_peptide ? 'success' : 'neutral'}
            />
            <ReportMetricCard label="置信度" value={`${Math.round(data.confidence * 100)}%`} tone="info" />
            <ReportMetricCard label="类型" value={data.predicted_type} />
            <ReportMetricCard label="切割位点" value={data.cleavage_site || 'N/A'} mono />
          </ReportMetricGrid>
        </ReportSection>

        <ReportSection title="Interpretation">
          <ReportPanel tone={data.has_signal_peptide ? 'success' : 'warning'} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {data.has_signal_peptide ? (
                <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
              ) : (
                <ShieldX className="h-4 w-4 text-amber-600 dark:text-amber-300" />
              )}
              <span className="text-sm font-medium">
                {data.has_signal_peptide ? '该序列具备分泌信号肽特征。' : '该序列未达到信号肽判定阈值。'}
              </span>
              {data.cache ? (
                <ReportBadge tone={data.cache.hit ? 'info' : 'neutral'}>
                  {data.cache.hit ? 'DB Cache' : 'Fresh'}
                </ReportBadge>
              ) : null}
            </div>
            {data.note ? <p className="text-xs leading-6 text-muted-foreground">{data.note}</p> : null}
          </ReportPanel>
        </ReportSection>

        <ReportSection title="Region Breakdown">
          <div className="grid gap-3 sm:grid-cols-3">
            <ReportPanel>
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">N-region</div>
              <div className="mt-2 text-sm font-semibold">带正电起始段</div>
              <div className="mt-1 text-xs text-muted-foreground">{formatRegion('n_region', data.regions.n_region)}</div>
            </ReportPanel>
            <ReportPanel>
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">H-region</div>
              <div className="mt-2 text-sm font-semibold">疏水核心</div>
              <div className="mt-1 text-xs text-muted-foreground">{formatRegion('h_region', data.regions.h_region)}</div>
            </ReportPanel>
            <ReportPanel>
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">C-region</div>
              <div className="mt-2 text-sm font-semibold">切割邻域</div>
              <div className="mt-1 text-xs text-muted-foreground">{formatRegion('c_region', data.regions.c_region)}</div>
            </ReportPanel>
          </div>
        </ReportSection>

        {data.cleavage_site ? (
          <ReportSection title="Cleavage Site">
            <ReportPanel tone="info" className="flex items-center gap-3">
              <code className="font-mono text-sm text-blue-700 dark:text-blue-300">{data.cleavage_site}</code>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">预测切割发生在该位点附近</span>
            </ReportPanel>
          </ReportSection>
        ) : null}
      </ReportBody>
    </ReportShell>
  )
}
