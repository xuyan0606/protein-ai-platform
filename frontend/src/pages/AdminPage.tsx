import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Building2, Database, Download, KeyRound, Loader2, ShieldCheck, SlidersHorizontal, UserCog, Users } from 'lucide-react'
import { api, ApiError, type AdminTaskAuditFilters, type AdminUser, type ApiAgentStrategyPolicy, type DeployDataImportRequest, type DeployDataReadiness, type Organization, type PermissionAudit, type ToolTaskAudit, type ToolTaskAuditSummary } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function formatTime(value?: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function roleLabel(role: string) {
  return role === 'admin' ? '管理员' : '研发用户'
}

function formatBytes(value?: number | null) {
  if (!value) return '0 B'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function statusClass(status: string) {
  if (status === 'ready') return 'bg-emerald-100 text-emerald-700'
  if (status === 'demo') return 'bg-amber-100 text-amber-700'
  if (status === 'empty') return 'bg-slate-100 text-slate-600'
  return 'bg-red-100 text-red-700'
}

function formatDuration(seconds?: number | null) {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

function cleanAuditFilters(filters: AdminTaskAuditFilters): AdminTaskAuditFilters {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== '' && value !== false)
  ) as AdminTaskAuditFilters
}

function policyStringList(policy: ApiAgentStrategyPolicy | null, key: string): string[] {
  const value = policy?.policy?.[key]
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item)).filter(Boolean)
}

function policyValue(policy: ApiAgentStrategyPolicy | null, key: string, fallback = '—') {
  const value = policy?.policy?.[key]
  if (value === undefined || value === null || value === '') return fallback
  return String(value)
}

export function AdminPage() {
  const currentUser = useAuthStore((state) => state.user)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [audits, setAudits] = useState<ToolTaskAudit[]>([])
  const [auditSummary, setAuditSummary] = useState<ToolTaskAuditSummary | null>(null)
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [permissionAudits, setPermissionAudits] = useState<PermissionAudit[]>([])
  const [dataReadiness, setDataReadiness] = useState<DeployDataReadiness | null>(null)
  const [strategyPolicy, setStrategyPolicy] = useState<ApiAgentStrategyPolicy | null>(null)
  const [dataUpdateFilters, setDataUpdateFilters] = useState<{ component?: string; status?: string }>({})
  const [filteredUpdates, setFilteredUpdates] = useState<DeployDataReadiness['updates']['manifests']>([])
  const [deployImport, setDeployImport] = useState<DeployDataImportRequest>({ symlink: true, dry_run: true })
  const [deployImportPlan, setDeployImportPlan] = useState<Record<string, unknown> | null>(null)
  const [state, setState] = useState<LoadState>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [auditFilters, setAuditFilters] = useState<AdminTaskAuditFilters>({})
  const [newOrgName, setNewOrgName] = useState('')
  const [orgMemberDrafts, setOrgMemberDrafts] = useState<Record<string, { email: string; role: 'member' | 'admin' }>>({})
  const [grantDrafts, setGrantDrafts] = useState<Record<string, { projectId: string; role: 'viewer' | 'editor' }>>({})

  const isAdmin = currentUser?.role === 'admin'

  const load = useCallback(async () => {
    if (!isAdmin) return
    setState('loading')
    setMessage(null)
    try {
      const [userResult, auditResult, readinessResult, organizationResult, permissionAuditResult, strategyPolicyResult] = await Promise.all([
        api.listAdminUsers(),
        api.listAdminTaskAudits(50, cleanAuditFilters(auditFilters)),
        api.getAdminDataReadiness(),
        api.listAdminOrganizations(),
        api.listAdminPermissionAudits(80),
        api.getAgentStrategyPolicy(),
      ])
      setUsers(userResult.users)
      setAudits(auditResult.audits)
      setAuditSummary(auditResult.summary || null)
      setDataReadiness(readinessResult)
      setFilteredUpdates(readinessResult.updates.manifests.filter((item) => item.exists))
      setOrganizations(organizationResult.organizations)
      setPermissionAudits(permissionAuditResult.audits)
      setStrategyPolicy(strategyPolicyResult)
      setState('ready')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '加载管理数据失败'
      setMessage(detail)
      setState('error')
    }
  }, [isAdmin, auditFilters])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) void load()
    })
    return () => {
      cancelled = true
    }
  }, [load])

  const updateRole = async (user: AdminUser, role: 'admin' | 'researcher') => {
    setMessage(null)
    try {
      const updated = await api.updateAdminUserRole(user.id, role)
      setUsers((items) => items.map((item) => item.id === updated.id ? updated : item))
      setMessage(`${updated.email} 已更新为${roleLabel(updated.role)}`)
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '角色更新失败'
      setMessage(detail)
    }
  }

  const updateUserStatus = async (
    user: AdminUser,
    payload: { is_active?: boolean; locked?: boolean; disabled_reason?: string | null },
  ) => {
    setMessage(null)
    try {
      const updated = await api.updateAdminUserStatus(user.id, payload)
      setUsers((items) => items.map((item) => item.id === updated.id ? updated : item))
      setMessage(`${updated.email} 状态已更新`)
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '用户状态更新失败'
      setMessage(detail)
    }
  }

  const reloadOrganizations = async () => {
    const [organizationResult, permissionAuditResult] = await Promise.all([
      api.listAdminOrganizations(),
      api.listAdminPermissionAudits(80),
    ])
    setOrganizations(organizationResult.organizations)
    setPermissionAudits(permissionAuditResult.audits)
  }

  const createOrganization = async () => {
    const name = newOrgName.trim()
    if (!name) return
    setMessage(null)
    try {
      await api.createAdminOrganization(name)
      setNewOrgName('')
      await reloadOrganizations()
      setMessage(`组织 ${name} 已创建`)
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '组织创建失败'
      setMessage(detail)
    }
  }

  const updateOrgMemberDraft = (organizationId: string, patch: Partial<{ email: string; role: 'member' | 'admin' }>) => {
    setOrgMemberDrafts((drafts) => ({
      ...drafts,
      [organizationId]: {
        email: drafts[organizationId]?.email || '',
        role: drafts[organizationId]?.role || 'member',
        ...patch,
      },
    }))
  }

  const addOrganizationMember = async (organizationId: string) => {
    const draft = orgMemberDrafts[organizationId] || { email: '', role: 'member' as const }
    if (!draft.email.trim()) return
    setMessage(null)
    try {
      await api.addAdminOrganizationMember(organizationId, draft.email.trim(), draft.role)
      setOrgMemberDrafts((drafts) => ({ ...drafts, [organizationId]: { email: '', role: draft.role } }))
      await reloadOrganizations()
      setMessage('组织成员已更新')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '组织成员更新失败'
      setMessage(detail)
    }
  }

  const updateOrganizationMember = async (organizationId: string, memberId: string, role: 'member' | 'admin') => {
    setMessage(null)
    try {
      await api.updateAdminOrganizationMember(organizationId, memberId, role)
      await reloadOrganizations()
      setMessage('组织成员角色已更新')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '组织成员角色更新失败'
      setMessage(detail)
    }
  }

  const removeOrganizationMember = async (organizationId: string, memberId: string) => {
    setMessage(null)
    try {
      await api.removeAdminOrganizationMember(organizationId, memberId)
      await reloadOrganizations()
      setMessage('组织成员已移除')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '组织成员移除失败'
      setMessage(detail)
    }
  }

  const updateGrantDraft = (organizationId: string, patch: Partial<{ projectId: string; role: 'viewer' | 'editor' }>) => {
    setGrantDrafts((drafts) => ({
      ...drafts,
      [organizationId]: {
        projectId: drafts[organizationId]?.projectId || '',
        role: drafts[organizationId]?.role || 'viewer',
        ...patch,
      },
    }))
  }

  const addProjectOrganizationGrant = async (organizationId: string) => {
    const draft = grantDrafts[organizationId] || { projectId: '', role: 'viewer' as const }
    if (!draft.projectId.trim()) return
    setMessage(null)
    try {
      await api.addProjectOrganizationGrant(draft.projectId.trim(), organizationId, draft.role)
      setGrantDrafts((drafts) => ({ ...drafts, [organizationId]: { projectId: '', role: draft.role } }))
      await reloadOrganizations()
      setMessage('项目组织授权已更新')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '项目组织授权失败；需要管理员权限或项目 owner 权限'
      setMessage(detail)
    }
  }

  const updateProjectOrganizationGrant = async (projectId: string, grantId: string, role: 'viewer' | 'editor') => {
    setMessage(null)
    try {
      await api.updateProjectOrganizationGrant(projectId, grantId, role)
      await reloadOrganizations()
      setMessage('项目组织授权角色已更新')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '项目组织授权角色更新失败'
      setMessage(detail)
    }
  }

  const removeProjectOrganizationGrant = async (projectId: string, grantId: string) => {
    setMessage(null)
    try {
      await api.removeProjectOrganizationGrant(projectId, grantId)
      await reloadOrganizations()
      setMessage('项目组织授权已撤销')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '项目组织授权撤销失败'
      setMessage(detail)
    }
  }

  const exportAudits = async () => {
    setMessage(null)
    try {
      const response = await api.exportAdminTaskAudits(500, cleanAuditFilters(auditFilters))
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'tool-task-audits.csv'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setMessage('任务审计 CSV 已开始下载')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '审计导出失败'
      setMessage(detail)
    }
  }

  const updateAuditFilter = (key: keyof AdminTaskAuditFilters, value: string | boolean) => {
    setAuditFilters((filters) => ({ ...filters, [key]: value }))
  }

  const loadDataUpdates = async (filters = dataUpdateFilters) => {
    setMessage(null)
    try {
      const result = await api.listAdminDeployDataUpdates({ ...filters, limit: 50 })
      setFilteredUpdates(result.updates.filter((item) => item.exists))
      setDataUpdateFilters(filters)
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '更新记录筛选失败'
      setMessage(detail)
    }
  }

  const updateDeployImport = (key: keyof DeployDataImportRequest, value: string | boolean) => {
    setDeployImport((current) => ({ ...current, [key]: value }))
  }

  const previewDeployImport = async () => {
    setMessage(null)
    try {
      const result = await api.triggerDeployDataImport({ ...deployImport, dry_run: true })
      setDeployImportPlan(result.plan || null)
      setMessage('已生成 deploy_data 导入 dry-run 计划，未写入任何文件')
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : '导入计划生成失败'
      setMessage(detail)
    }
  }

  const activeUserCount = users.filter((item) => item.is_active !== false).length
  const lockedUserCount = users.filter((item) => item.locked_at).length
  const failedTaskCount = auditSummary
    ? Object.values(auditSummary.failure_counts || {}).reduce((sum, value) => sum + value, 0)
    : 0

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <div className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6 text-center">
          <div className="mb-5 rounded-3xl border border-amber-300/30 bg-amber-300/10 p-5 text-amber-200">
            <AlertTriangle className="h-10 w-10" />
          </div>
          <h1 className="text-3xl font-semibold">需要管理员权限</h1>
          <p className="mt-3 max-w-xl text-sm leading-7 text-slate-300">
            当前账号没有管理后台权限。后端接口也会强制校验 `admin` 角色，不能仅靠前端绕过。
          </p>
          <Link
            to="/home"
            className="mt-7 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
          >
            返回首页
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-slate-100 text-slate-950">
      <header className="border-b border-black/10 bg-[#17231f] text-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-5 px-6 py-7 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-emerald-300/10 px-3 py-1 text-xs font-medium text-emerald-100">
              <ShieldCheck className="h-4 w-4" />
              Admin Console
            </div>
            <h1 className="text-3xl font-semibold tracking-tight">平台管理后台</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              管理用户角色、查看跨用户任务审计，并导出脱敏审计 CSV。
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => void load()}
              disabled={state === 'loading'}
              className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:opacity-60"
            >
              {state === 'loading' ? '刷新中...' : '刷新'}
            </button>
            <Link
              to="/home"
              className="rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-200"
            >
              返回首页
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-7">
        {message && (
          <div className="mb-5 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
            {message}
          </div>
        )}

        {state === 'loading' && (
          <div className="mb-5 flex items-center gap-2 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载管理数据
          </div>
        )}

        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: '用户总数', value: users.length, hint: `${activeUserCount} 启用` },
            { label: '锁定用户', value: lockedUserCount, hint: '需人工处理' },
            { label: '审计任务', value: auditSummary?.total ?? audits.length, hint: `${failedTaskCount} 失败` },
            { label: '组织数量', value: organizations.length, hint: `${permissionAudits.length} 条权限审计` },
          ].map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="text-xs font-medium text-slate-500">{item.label}</div>
              <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">{item.value}</div>
              <div className="mt-1 text-xs text-slate-500">{item.hint}</div>
            </div>
          ))}
        </div>

        <section className="mb-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <SlidersHorizontal className="h-4 w-4" />
                Agent 策略治理
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                只读展示当前会话策略判定规则。修改必须通过 `AGENT_STRATEGY_POLICY_JSON` 配置和发布流程完成。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                strategyPolicy?.status === 'default_due_to_error'
                  ? 'bg-red-100 text-red-700'
                  : strategyPolicy?.status === 'configured'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-700'
              }`}>
                {strategyPolicy?.status || 'loading'}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                v{policyValue(strategyPolicy, 'version')}
              </span>
            </div>
          </div>

          {strategyPolicy?.parse_error && (
            <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-800">
              配置解析错误：{strategyPolicy.parse_error}。系统已回退默认策略，避免半生效规则影响确认执行和续问判断。
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs font-semibold text-slate-900">关键开关</div>
              <div className="mt-3 grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
                <div className="rounded-xl bg-white px-3 py-2">
                  手输确认最大长度：{policyValue(strategyPolicy, 'max_typed_confirmation_chars')}
                </div>
                <div className="rounded-xl bg-white px-3 py-2">
                  历史 raw 序列需显式续问：{policyValue(strategyPolicy, 'raw_sequence_history_requires_continuation')}
                </div>
              </div>
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                风险提示：策略 token 只决定“续问、确认、新任务、重启”的状态机边界；不会提升干实验预测证据等级，也不能把计算假设写成湿实验结论。
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {[
                { key: 'continuation_tokens', label: '同题续问 token' },
                { key: 'new_task_tokens', label: '新任务 token' },
                { key: 'followup_synthesis_tokens', label: '解释整理 token' },
                { key: 'execution_tokens', label: '执行/重启排除 token' },
                { key: 'confirmation_tokens', label: '确认短句 token' },
              ].map((group) => {
                const tokens = policyStringList(strategyPolicy, group.key)
                return (
                  <div key={group.key} className="rounded-2xl border border-slate-200 bg-white p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-slate-900">{group.label}</div>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{tokens.length}</span>
                    </div>
                    <div className="mt-2 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto pr-1">
                      {tokens.map((token) => (
                        <span key={`${group.key}-${token}`} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-700">
                          {token}
                        </span>
                      ))}
                      {tokens.length === 0 && (
                        <span className="text-xs text-slate-500">暂无配置</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        <div className="space-y-6">
          <section className="min-w-0 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Users className="h-4 w-4" />
                  用户与角色
                </div>
                <p className="mt-1 text-xs text-slate-500">仅支持 `admin` / `researcher` 两档角色。</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {users.length} users
              </span>
            </div>

            <div className="max-h-[36rem] max-w-full min-w-0 overflow-x-auto overflow-y-auto rounded-2xl border border-slate-200">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">用户</th>
                    <th className="px-4 py-3">角色</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-4 py-3">创建时间</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((user) => (
                    <tr key={user.id} className="align-top">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{user.name}</div>
                        <div className="text-xs text-slate-500">{user.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          user.role === 'admin' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {roleLabel(user.role)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-medium ${
                            user.is_active === false ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
                          }`}>
                            {user.is_active === false ? '已禁用' : '启用'}
                          </span>
                          {user.locked_at && (
                            <span className="w-fit rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800">
                              已锁定
                            </span>
                          )}
                          {user.disabled_reason && (
                            <span className="max-w-[10rem] truncate text-xs text-slate-500" title={user.disabled_reason}>
                              {user.disabled_reason}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{formatTime(user.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <select
                            value={user.role}
                            onChange={(event) => void updateRole(user, event.target.value as 'admin' | 'researcher')}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 outline-none transition focus:border-emerald-500"
                          >
                            <option value="researcher">研发用户</option>
                            <option value="admin">管理员</option>
                          </select>
                          <button
                            onClick={() => void updateUserStatus(user, {
                              is_active: user.is_active === false,
                              disabled_reason: user.is_active === false ? null : 'disabled by admin',
                            })}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                          >
                            {user.is_active === false ? '启用' : '禁用'}
                          </button>
                          <button
                            onClick={() => void updateUserStatus(user, { locked: !user.locked_at })}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                          >
                            {user.locked_at ? '解锁' : '锁定'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-sm text-slate-500">
                        暂无用户数据
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Activity className="h-4 w-4" />
                  任务审计
                </div>
                <p className="mt-1 text-xs text-slate-500">跨用户任务状态、队列、耗时策略和结果摘要。</p>
              </div>
              <button
                onClick={() => void exportAudits()}
                className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
              >
                <Download className="h-4 w-4" />
                导出 CSV
              </button>
            </div>

            <div className="mb-4 rounded-2xl border border-black/10 bg-white p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-xs font-semibold text-slate-900">筛选条件</div>
                <button
                  onClick={() => setAuditFilters({})}
                  className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
                >
                  重置
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <input
                  value={auditFilters.tool || ''}
                  onChange={(event) => updateAuditFilter('tool', event.target.value)}
                  placeholder="工具名，如 gromacs_md"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                />
                <select
                  value={auditFilters.status || ''}
                  onChange={(event) => updateAuditFilter('status', event.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                >
                  <option value="">全部状态</option>
                  <option value="submitted">submitted</option>
                  <option value="running">running</option>
                  <option value="completed">completed</option>
                  <option value="failed">failed</option>
                  <option value="canceled">canceled</option>
                </select>
                <input
                  value={auditFilters.queue || ''}
                  onChange={(event) => updateAuditFilter('queue', event.target.value)}
                  placeholder="队列，如 md_cpu"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                />
                <select
                  value={auditFilters.failure_class || ''}
                  onChange={(event) => updateAuditFilter('failure_class', event.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                >
                  <option value="">全部失败分类</option>
                  <option value="timeout">timeout</option>
                  <option value="permission">permission</option>
                  <option value="missing_input">missing_input</option>
                  <option value="md_runtime">md_runtime</option>
                  <option value="runtime_error">runtime_error</option>
                  <option value="canceled">canceled</option>
                </select>
                <input
                  type="datetime-local"
                  value={auditFilters.submitted_after || ''}
                  onChange={(event) => updateAuditFilter('submitted_after', event.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                />
                <input
                  type="datetime-local"
                  value={auditFilters.submitted_before || ''}
                  onChange={(event) => updateAuditFilter('submitted_before', event.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                />
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(auditFilters.failed_only)}
                    onChange={(event) => updateAuditFilter('failed_only', event.target.checked)}
                  />
                  仅失败/取消
                </label>
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(auditFilters.slow_only)}
                    onChange={(event) => updateAuditFilter('slow_only', event.target.checked)}
                  />
                  仅慢任务
                </label>
              </div>
            </div>

            {auditSummary && (
              <div className="mb-4 space-y-3">
                <div className="grid gap-2 text-xs text-slate-700 sm:grid-cols-4">
                  <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                    <div className="text-slate-500">总任务</div>
                    <div className="mt-1 text-xl font-semibold text-slate-950">{auditSummary.total}</div>
                  </div>
                  <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                    <div className="text-slate-500">失败任务</div>
                    <div className="mt-1 text-xl font-semibold text-red-700">
                      {Object.values(auditSummary.failure_counts || {}).reduce((sum, value) => sum + value, 0)}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                    <div className="text-slate-500">慢任务</div>
                    <div className="mt-1 text-xl font-semibold text-amber-700">{auditSummary.slow_count}</div>
                  </div>
                  <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                    <div className="text-slate-500">平均耗时</div>
                    <div className="mt-1 text-xl font-semibold text-slate-950">{formatDuration(auditSummary.duration?.mean_seconds)}</div>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-black/10 bg-white px-3 py-3 text-xs">
                    <div className="font-semibold text-slate-900">失败分类</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Object.entries(auditSummary.failure_counts || {}).map(([name, count]) => (
                        <span key={name} className="rounded-full bg-red-50 px-2.5 py-1 text-red-700">{name}: {count}</span>
                      ))}
                      {Object.keys(auditSummary.failure_counts || {}).length === 0 && <span className="text-slate-500">暂无失败</span>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-black/10 bg-white px-3 py-3 text-xs">
                    <div className="font-semibold text-slate-900">运行环境</div>
                    <div className="mt-2 space-y-1 text-slate-600">
                      <div>Python: {auditSummary.runtime_environment?.python_version || '—'}</div>
                      <div>Machine: {auditSummary.runtime_environment?.machine || '—'}</div>
                      <div className="truncate">Platform: {auditSummary.runtime_environment?.platform || '—'}</div>
                    </div>
                  </div>
                </div>
                {auditSummary.failure_trend && auditSummary.failure_trend.length > 0 && (
                  <div className="rounded-2xl border border-black/10 bg-white px-3 py-3 text-xs">
                    <div className="font-semibold text-slate-900">失败日期趋势</div>
                    <div className="mt-3 grid gap-2">
                      {auditSummary.failure_trend.slice(-7).map((bucket) => (
                        <div key={bucket.date} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-3 py-2">
                          <span className="font-medium text-slate-800">{bucket.date}</span>
                          <span className="text-red-700">{bucket.total_failures} failures</span>
                          <span className="min-w-0 break-words text-slate-500">
                            {Object.entries(bucket.failure_counts).map(([name, count]) => `${name}:${count}`).join(' · ')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {auditSummary.alerting && (
                  <div className={`rounded-2xl border px-3 py-3 text-xs ${
                    auditSummary.alerting.status === 'triggered'
                      ? 'border-amber-200 bg-amber-50 text-amber-900'
                      : 'border-emerald-100 bg-emerald-50 text-emerald-800'
                  }`}>
                    <div className="font-semibold">告警联动状态：{auditSummary.alerting.status}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {auditSummary.alerting.rules.map((rule) => (
                        <span key={rule.name} className="rounded-full bg-white/70 px-2.5 py-1">
                          {rule.name}: {rule.observed}/{rule.threshold}
                        </span>
                      ))}
                      <span className="rounded-full bg-white/70 px-2.5 py-1">
                        外部发送：{auditSummary.alerting.external_delivery}
                      </span>
                    </div>
                  </div>
                )}
                {auditSummary.recent_failures?.length > 0 && (
                  <div className="rounded-2xl border border-red-100 bg-red-50 px-3 py-3 text-xs text-red-800">
                    <div className="font-semibold">最近失败任务</div>
                    <div className="mt-2 grid gap-1.5">
                      {auditSummary.recent_failures.slice(0, 5).map((failure) => (
                        <div key={failure.task_id} className="flex flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 break-all font-mono">{failure.task_id}</span>
                          <span className="min-w-0 break-words">{failure.tool} · {failure.failure_class} · {formatTime(failure.updated_at)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="grid max-h-[44rem] gap-3 overflow-y-auto pr-1 xl:grid-cols-2">
              {audits.map((audit) => (
                <div key={audit.id || audit.task_id} className="min-w-0 rounded-2xl border border-black/10 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="break-all font-mono text-xs text-slate-500">{audit.task_id}</div>
                      <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
                        <span className="min-w-0 break-words font-medium text-slate-900">{audit.tool}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                          {audit.status}
                        </span>
                      </div>
                    </div>
                    <div className="min-w-0 text-right text-xs text-slate-500">
                      <div>User #{audit.user_id}</div>
                      <div>{formatTime(audit.updated_at || audit.submitted_at)}</div>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
                    <div className="rounded-xl bg-slate-50 px-3 py-2">队列：{audit.queue || '—'}</div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2">进度：{audit.progress ?? '—'}</div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2">耗时：{formatDuration(audit.duration_seconds)}</div>
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
                    <div className="rounded-xl bg-slate-50 px-3 py-2">阶段：{audit.stage || '—'}</div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2">失败分类：{audit.failure_class || '—'}</div>
                    <div className={`rounded-xl px-3 py-2 ${audit.is_slow ? 'bg-amber-100 text-amber-800' : 'bg-slate-50'}`}>
                      慢任务：{audit.is_slow ? '是' : '否'}
                    </div>
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div className="rounded-xl bg-slate-50 px-3 py-2">Python：{audit.runtime_environment?.python_version || '—'}</div>
                    <div className="min-w-0 break-all rounded-xl bg-slate-50 px-3 py-2">平台：{audit.runtime_environment?.platform || '—'}</div>
                  </div>
                  {audit.error && (
                    <div className="mt-3 break-words rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                      {audit.error}
                    </div>
                  )}
                </div>
              ))}
              {audits.length === 0 && (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 px-4 py-10 text-center text-sm text-slate-500">
                  暂无任务审计记录
                </div>
              )}
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Building2 className="h-4 w-4" />
                组织与项目授权
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                管理团队成员，并把组织以 viewer/editor 身份授权到项目。项目授权支持管理员或项目 owner 操作。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                value={newOrgName}
                onChange={(event) => setNewOrgName(event.target.value)}
                placeholder="新组织名称"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
              />
              <button
                onClick={() => void createOrganization()}
                className="rounded-full bg-slate-950 px-4 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
              >
                创建组织
              </button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              {organizations.map((organization) => {
                const memberDraft = orgMemberDrafts[organization.id] || { email: '', role: 'member' as const }
                const grantDraft = grantDrafts[organization.id] || { projectId: '', role: 'viewer' as const }
                return (
                  <div key={organization.id} className="rounded-3xl border border-black/10 bg-white p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-slate-900">{organization.name}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          ID {organization.id} · Owner #{organization.owner_user_id} · {organization.members.length} members
                        </div>
                      </div>
                      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
                        {organization.project_grants.length} project grants
                      </span>
                    </div>

                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-900">
                          <Users className="h-4 w-4" />
                          成员
                        </div>
                        <div className="space-y-2">
                          {organization.members.map((member) => (
                            <div key={member.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-3 py-2 text-xs">
                              <div>
                                <div className="font-medium text-slate-900">{member.name || member.email || `User #${member.user_id}`}</div>
                                <div className="text-slate-500">{member.email || `User #${member.user_id}`}</div>
                              </div>
                              <div className="flex items-center gap-2">
                                <select
                                  value={member.role}
                                  onChange={(event) => void updateOrganizationMember(organization.id, member.id, event.target.value as 'member' | 'admin')}
                                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs outline-none focus:border-emerald-500"
                                >
                                  <option value="member">member</option>
                                  <option value="admin">admin</option>
                                </select>
                                <button
                                  onClick={() => void removeOrganizationMember(organization.id, member.id)}
                                  className="rounded-lg border border-red-100 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 transition hover:bg-red-100"
                                >
                                  移除
                                </button>
                              </div>
                            </div>
                          ))}
                          {organization.members.length === 0 && (
                            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-3 py-4 text-center text-xs text-slate-500">
                              暂无成员
                            </div>
                          )}
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                          <input
                            value={memberDraft.email}
                            onChange={(event) => updateOrgMemberDraft(organization.id, { email: event.target.value })}
                            placeholder="成员邮箱"
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                          />
                          <select
                            value={memberDraft.role}
                            onChange={(event) => updateOrgMemberDraft(organization.id, { role: event.target.value as 'member' | 'admin' })}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                          >
                            <option value="member">member</option>
                            <option value="admin">admin</option>
                          </select>
                          <button
                            onClick={() => void addOrganizationMember(organization.id)}
                            className="rounded-xl bg-slate-950 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
                          >
                            添加
                          </button>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-200 bg-[#fffaf1] p-3">
                        <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-900">
                          <KeyRound className="h-4 w-4" />
                          项目授权
                        </div>
                        <div className="space-y-2">
                          {organization.project_grants.map((grant) => (
                            <div key={grant.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-3 py-2 text-xs">
                              <div>
                                <div className="font-medium text-slate-900">{grant.project_name || grant.project_id}</div>
                                <div className="font-mono text-slate-500">{grant.project_id}</div>
                              </div>
                              <div className="flex items-center gap-2">
                                <select
                                  value={grant.role}
                                  onChange={(event) => void updateProjectOrganizationGrant(grant.project_id, grant.id, event.target.value as 'viewer' | 'editor')}
                                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs outline-none focus:border-emerald-500"
                                >
                                  <option value="viewer">viewer</option>
                                  <option value="editor">editor</option>
                                </select>
                                <button
                                  onClick={() => void removeProjectOrganizationGrant(grant.project_id, grant.id)}
                                  className="rounded-lg border border-red-100 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 transition hover:bg-red-100"
                                >
                                  撤销
                                </button>
                              </div>
                            </div>
                          ))}
                          {organization.project_grants.length === 0 && (
                            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-3 py-4 text-center text-xs text-slate-500">
                              暂无项目授权
                            </div>
                          )}
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                          <input
                            value={grantDraft.projectId}
                            onChange={(event) => updateGrantDraft(organization.id, { projectId: event.target.value })}
                            placeholder="项目 ID"
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-emerald-500"
                          />
                          <select
                            value={grantDraft.role}
                            onChange={(event) => updateGrantDraft(organization.id, { role: event.target.value as 'viewer' | 'editor' })}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                          >
                            <option value="viewer">viewer</option>
                            <option value="editor">editor</option>
                          </select>
                          <button
                            onClick={() => void addProjectOrganizationGrant(organization.id)}
                            className="rounded-xl bg-slate-950 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
                          >
                            授权
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
              {organizations.length === 0 && (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 px-4 py-10 text-center text-sm text-slate-500">
                  暂无组织。创建组织后可添加成员并授权到项目。
                </div>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">权限审计</div>
                  <div className="mt-1 text-xs text-slate-500">最近 {permissionAudits.length} 条项目/组织权限变更。</div>
                </div>
                <button
                  onClick={() => void reloadOrganizations()}
                  className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
                >
                  刷新
                </button>
              </div>
              <div className="max-h-[32rem] space-y-2 overflow-y-auto pr-1">
                {permissionAudits.map((audit) => (
                  <div key={audit.id} className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-slate-900">{audit.action}</span>
                      <span>{formatTime(audit.created_at)}</span>
                    </div>
                    <div className="mt-1 grid gap-1 sm:grid-cols-2">
                      <span>actor: {audit.actor_user_id ?? '—'}</span>
                      <span>target: {audit.target_user_id ?? '—'}</span>
                      <span className="truncate">project: {audit.project_id || '—'}</span>
                      <span className="truncate">org: {audit.organization_id || '—'}</span>
                    </div>
                    <div className="mt-1 text-slate-500">
                      role: {audit.role_before || '—'} → {audit.role_after || '—'}
                    </div>
                  </div>
                ))}
                {permissionAudits.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                    暂无权限审计记录
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Database className="h-4 w-4" />
                数据资产状态
              </div>
              <p className="mt-1 text-xs text-slate-500">
                只读检查 `deploy_data` 中 PDB、AlphaFold、SIFTS、注释库和 Foldseek DB 的就绪度。
              </p>
            </div>
            {dataReadiness && (
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${dataReadiness.live_ready ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                  {dataReadiness.summary}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                  {dataReadiness.root.project_relative_path}
                </span>
              </div>
            )}
          </div>

          {dataReadiness ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {Object.entries(dataReadiness.components).map(([name, component]) => {
                  const count = typeof component.count === 'number'
                    ? component.count
                    : Object.values(component.counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
                  return (
                    <div key={name} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium capitalize text-slate-900">{name.replace('_', ' ')}</div>
                          <div className="mt-1 max-w-[18rem] truncate text-xs text-slate-500" title={component.path.path}>
                            {component.path.project_relative_path}
                          </div>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(component.status)}`}>
                          {component.status}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-600">
                        <div className="rounded-xl bg-white px-3 py-2">数量：{count}</div>
                        <div className="rounded-xl bg-white px-3 py-2">大小：{formatBytes(component.size_bytes)}</div>
                      </div>
                      {component.failure_reason && (
                        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                          {component.failure_reason}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {dataReadiness.version_comparison && (
                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-semibold text-slate-900">数据版本对比</div>
                  <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-3">
                    <div className="rounded-xl bg-white px-3 py-2">
                      最新 manifest：{dataReadiness.version_comparison.latest_manifest?.label || '—'}
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2">
                      已就绪：{dataReadiness.version_comparison.ready_components.length}
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2">
                      未就绪：{dataReadiness.version_comparison.not_ready_components.join(', ') || '—'}
                    </div>
                  </div>
                </div>
              )}

              {dataReadiness.next_actions.length > 0 && (
                <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <div className="text-sm font-semibold text-amber-900">下一步动作</div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {dataReadiness.next_actions.map((action) => (
                      <div key={action} className="rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 text-amber-900">
                        {action}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="text-sm font-semibold text-slate-900">更新记录</div>
                  <div className="flex flex-wrap gap-2">
                    <select
                      value={dataUpdateFilters.component || ''}
                      onChange={(event) => void loadDataUpdates({ ...dataUpdateFilters, component: event.target.value || undefined })}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                    >
                      <option value="">全部组件</option>
                      {(dataReadiness.updates.filters?.components || []).map((component) => (
                        <option key={component} value={component}>{component}</option>
                      ))}
                    </select>
                    <select
                      value={dataUpdateFilters.status || ''}
                      onChange={(event) => void loadDataUpdates({ ...dataUpdateFilters, status: event.target.value || undefined })}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                    >
                      <option value="">全部状态</option>
                      {(dataReadiness.updates.filters?.statuses || []).map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </div>
                </div>
                {dataReadiness.updates.manifest_count > 0 ? (
                  <div className="grid gap-2 md:grid-cols-2">
                    {filteredUpdates.map((item) => (
                      <div key={item.project_relative_path} className="rounded-xl bg-white px-3 py-2 text-xs text-slate-600">
                        <div className="flex items-center justify-between gap-2">
                          <div className="font-medium text-slate-900">{item.label}</div>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5">{item.status || 'unknown'}</span>
                        </div>
                        <div className="mt-1 truncate" title={item.path}>{item.project_relative_path}</div>
                        <div className="mt-1">更新时间：{item.updated_at || '—'} · 版本：{item.version || '—'} · {formatBytes(item.size_bytes)}</div>
                        {item.failure_reason && <div className="mt-1 text-red-700">{item.failure_reason}</div>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">
                    暂无 live/import/bundle manifest 更新记录
                  </div>
                )}
              </div>

              <div className="mt-5 rounded-2xl border border-slate-200 bg-[#f7fbf4] p-4">
                <div className="text-sm font-semibold text-slate-900">真实数据导入计划</div>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  默认只生成 dry-run 计划，不复制、不覆盖、不建立链接。真实执行需后端确认令牌。
                </p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {([
                    ['annotations', 'annotations 源路径'],
                    ['sifts', 'SIFTS 源路径'],
                    ['pdb', 'PDB 源路径'],
                    ['alphafold', 'AlphaFold 源路径'],
                    ['foldseek_root', 'Foldseek DB 根路径'],
                    ['smoke_pdb', 'Smoke PDB 文件路径'],
                  ] as Array<[keyof DeployDataImportRequest, string]>).map(([key, placeholder]) => (
                    <input
                      key={key}
                      value={String(deployImport[key] || '')}
                      onChange={(event) => updateDeployImport(key, event.target.value)}
                      placeholder={placeholder}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-500"
                    />
                  ))}
                </div>
                <label className="mt-3 flex items-center gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={deployImport.symlink !== false}
                    onChange={(event) => updateDeployImport('symlink', event.target.checked)}
                  />
                  使用 symlink 接入真实数据，避免复制大文件
                </label>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => void previewDeployImport()}
                    className="rounded-full bg-slate-950 px-4 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
                  >
                    生成 dry-run 导入计划
                  </button>
                  {deployImportPlan && (
                    <span className="text-xs text-slate-600">
                      命令：{Array.isArray(deployImportPlan.command) ? deployImportPlan.command.join(' ') : '已生成'}
                    </span>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              暂无数据资产状态
            </div>
          )}
        </section>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <UserCog className="mt-1 h-5 w-5 text-emerald-700" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">权限边界说明</h2>
              <p className="mt-1 text-sm leading-7 text-slate-600">
                当前管理后台只开放角色管理和审计导出。项目级 ACL、访客只读、备份恢复、版本升级仍应继续作为后续批次推进。
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
