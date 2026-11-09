// New responses carry the server projection. The fallback handles saved chats
// from before the execution/evidence states were separated.
export function toolResultDisplayStatus(execution: string, value: unknown, supplied?: unknown): string {
  if (supplied && typeof supplied === 'object') {
    const display = (supplied as Record<string, unknown>).display_status
    if (typeof display === 'string') return display
  }
  if (!['completed', 'degraded'].includes(execution)) return execution
  if (!value || typeof value !== 'object') return execution
  const payload = value as Record<string, unknown>
  const status = String(payload.status || '').toLowerCase()
  const source = payload.evidence_source as Record<string, unknown> | undefined
  if (['blocked', 'failed', 'failure', 'not_available', 'not_run', 'stale_cache', 'degraded', 'cancelled', 'canceled'].includes(status)
    || ['blocked', 'degraded'].includes(String(source?.status || ''))) return 'blocked'
  if (['submitted', 'pending', 'running', 'waiting', 'submitting', 'retry', 'queued'].includes(status)) return status
  if (status === 'partial') return 'partial'
  if (status === 'completed_no_hit' || (payload.results_count === 0 && payload.search_executed !== false && !payload.query_structure)) return 'empty'
  return execution
}

export const TOOL_RESULT_LABELS: Record<string, string> = {
  completed: '结果可用', blocked: '结果不可用', partial: '部分结果可用', empty: '检索完成，无命中',
}
