import { Boxes, Sparkles } from 'lucide-react'
import type { AnnotationBundleData } from '@/components/analysis/AnnotationBundleResult'
import { CatalyticSiteCard } from '@/components/analysis/CatalyticSiteCard'
import { InterProAnnotationCard } from '@/components/analysis/InterProAnnotationCard'
import { isCatalyticSiteResult, isInterProAnnotationResult, isSignalPeptideResult } from '@/components/analysis/resultGuards'
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
import { SignalPeptideCard } from '@/components/analysis/SignalPeptideCard'

function getInterproCount(data: AnnotationBundleData): number {
  return isInterProAnnotationResult(data.interpro) ? data.interpro.annotations.length : 0
}

function getProtectedCount(data: AnnotationBundleData): number {
  return isCatalyticSiteResult(data.catalytic_sites) ? data.catalytic_sites.protected_positions.length : 0
}

function hasSignalPeptide(data: AnnotationBundleData): boolean {
  return isSignalPeptideResult(data.signal_peptide) ? data.signal_peptide.has_signal_peptide : false
}

function primaryEc(data: AnnotationBundleData): string {
  const entries = data.protein?.ec_numbers
  if (!entries?.length) return 'Not curated'
  const primary = entries.find((entry) => entry.primary) || entries[0]
  return primary.ec || 'Not curated'
}

export function AnnotationBundleCard({ data }: { data: AnnotationBundleData }) {
  const interproCount = getInterproCount(data)
  const protectedCount = getProtectedCount(data)
  const signalDetected = hasSignalPeptide(data)
  const signalCache = isSignalPeptideResult(data.signal_peptide) ? data.signal_peptide.cache : null

  return (
    <div className="space-y-4">
      <ReportShell>
        <ReportHeader
          icon={Boxes}
          title="注释工具包"
          subtitle={`${data.query?.sequence_length ?? '-'} aa · ${data.query?.uniprot_id || 'sequence mode'}`}
          badge={
            <ReportBadge tone={data.query?.has_curated_enzyme ? 'success' : 'warning'}>
              {data.query?.has_curated_enzyme ? 'Curated Record' : 'Sequence Fallback'}
            </ReportBadge>
          }
        />
        <ReportBody>
          {data.error ? (
            <ReportPanel tone="danger" className="text-xs text-red-700 dark:text-red-300">
              {data.error}
            </ReportPanel>
          ) : null}

          <ReportSection title="Bundle Summary" icon={Sparkles}>
            <ReportMetricGrid>
              <ReportMetricCard label="InterPro 条目" value={interproCount} tone="success" />
              <ReportMetricCard label="保护位点" value={protectedCount} tone="danger" />
              <ReportMetricCard label="EC / 功能" value={primaryEc(data)} tone={data.protein?.ec_numbers?.length ? 'success' : 'neutral'} />
              <ReportMetricCard label="信号肽" value={signalDetected ? 'Detected' : 'Not Detected'} tone={signalDetected ? 'success' : 'neutral'} />
              <ReportMetricCard label="数据来源" value={data.query?.has_curated_enzyme ? 'Curated + Local DB' : 'Sequence Fallback'} tone={data.query?.has_curated_enzyme ? 'success' : 'warning'} />
            </ReportMetricGrid>
          </ReportSection>

          <ReportPanel tone={data.query?.has_curated_enzyme ? 'success' : 'warning'} className="text-xs leading-6 text-muted-foreground">
            {data.query?.has_curated_enzyme
              ? 'This bundle is backed by a curated local enzyme record and merged with local annotation services.'
              : 'This bundle is running in sequence fallback mode. Some entries may come from heuristics instead of curated protein records.'}
            {signalCache ? (
              <>
                {' '}Signal peptide cache: <strong>{signalCache.hit ? 'hit' : 'fresh'}</strong> ({signalCache.source}).
              </>
            ) : null}
          </ReportPanel>
          <ReportPanel tone={data.coordinate_system?.status === 'verified' ? 'success' : 'warning'} className="text-xs leading-6 text-muted-foreground">
            <strong>坐标状态：</strong>{data.coordinate_system?.status || 'not_available'}。{' '}
            {data.coordinate_system?.note || '没有可复用的 curated 坐标映射。'}
          </ReportPanel>
          {data.protein?.function_annotation || data.protein?.catalytic_activity || data.protein?.cofactors ? (
            <ReportPanel tone="neutral" className="space-y-1 text-xs leading-6 text-muted-foreground">
              {data.protein?.protein_name ? <div><strong>蛋白：</strong>{data.protein.protein_name}</div> : null}
              {data.protein?.function_annotation ? <div><strong>功能：</strong>{data.protein.function_annotation}</div> : null}
              {data.protein?.catalytic_activity ? <div><strong>反应：</strong>{data.protein.catalytic_activity}</div> : null}
              {data.protein?.cofactors ? <div><strong>辅因子：</strong>{Array.isArray(data.protein.cofactors) ? data.protein.cofactors.join(', ') : String(data.protein.cofactors)}</div> : null}
            </ReportPanel>
          ) : null}
        </ReportBody>
      </ReportShell>

      {isInterProAnnotationResult(data.interpro) ? <InterProAnnotationCard data={data.interpro} /> : null}
      {isCatalyticSiteResult(data.catalytic_sites) ? <CatalyticSiteCard data={data.catalytic_sites} /> : null}
      {isSignalPeptideResult(data.signal_peptide) ? <SignalPeptideCard data={data.signal_peptide} /> : null}
    </div>
  )
}
