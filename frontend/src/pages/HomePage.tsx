import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/auth'
import { BrandLogo } from '@/components/BrandLogo'
import {
  Dna, Beaker, Zap, ArrowRight, Sparkles, Upload,
  Microscope, Thermometer, GitCompare, Scissors, ChevronRight,
  BookOpen,
  Activity,
  ShieldCheck,
} from 'lucide-react'
import { useRef } from 'react'

const QUICK_ANALYSES = [
  {
    icon: Microscope,
    titleKey: 'home.analyzeStability',
    color: 'bg-blue-500/10 text-blue-500 border-blue-500/20 hover:border-blue-500/40',
    promptKey: 'home.promptStability',
  },
  {
    icon: Thermometer,
    titleKey: 'home.designMutations',
    color: 'bg-amber-500/10 text-amber-500 border-amber-500/20 hover:border-amber-500/40',
    promptKey: 'home.promptMutations',
  },
  {
    icon: GitCompare,
    titleKey: 'home.benchmark',
    color: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20 hover:border-emerald-500/40',
    promptKey: 'home.promptBenchmark',
  },
  {
    icon: Scissors,
    titleKey: 'home.docking',
    color: 'bg-purple-500/10 text-purple-500 border-purple-500/20 hover:border-purple-500/40',
    promptKey: 'home.promptDocking',
  },
  {
    icon: Activity,
    titleKey: 'home.mdValidation',
    color: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20 hover:border-cyan-500/40',
    promptKey: 'home.promptMdValidation',
  },
  {
    icon: Dna,
    titleKey: 'home.predictStructure',
    color: 'bg-rose-500/10 text-rose-500 border-rose-500/20 hover:border-rose-500/40',
    promptKey: 'home.promptStructure',
  },
  {
    icon: Beaker,
    titleKey: 'home.solubility',
    color: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20 hover:border-cyan-500/40',
    promptKey: 'home.promptSolubility',
  },
]

const TOOL_CATEGORIES = [
  {
    name: 'design',
    label: 'Protein Design',
    icon: Beaker,
    desc: 'Sequence & structure design tools',
    tone: 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/15',
  },
  {
    name: 'prediction',
    label: 'Prediction',
    icon: Zap,
    desc: 'Structure & property prediction',
    tone: 'bg-blue-500/10 text-blue-600 ring-blue-500/15',
  },
  {
    name: 'simulation',
    label: 'Simulation',
    icon: Microscope,
    desc: 'MD & dynamics simulation',
    tone: 'bg-cyan-500/10 text-cyan-600 ring-cyan-500/15',
  },
  {
    name: 'search',
    label: 'Search',
    icon: GitCompare,
    desc: 'Sequence & database search',
    tone: 'bg-violet-500/10 text-violet-600 ring-violet-500/15',
  },
  {
    name: 'engineering',
    label: 'Engineering',
    icon: Thermometer,
    desc: 'Mutation & optimization',
    tone: 'bg-amber-500/10 text-amber-600 ring-amber-500/15',
  },
  {
    name: 'docking',
    label: 'Docking',
    icon: Scissors,
    desc: 'Molecular docking tools',
    tone: 'bg-rose-500/10 text-rose-600 ring-rose-500/15',
  },
  {
    name: 'analysis',
    label: 'Analysis',
    icon: Sparkles,
    desc: 'Data analysis & scoring',
    tone: 'bg-slate-500/10 text-slate-600 ring-slate-500/15',
  },
  {
    name: 'capabilities',
    label: '能力边界',
    icon: ShieldCheck,
    desc: '查看 live、proxy、blocked 与升级条件',
    href: '/data?tab=capabilities',
    tone: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/15',
  },
  {
    name: 'research',
    label: 'Research Gates',
    icon: ShieldCheck,
    desc: 'Training, claim, delivery, release status',
    href: '/research',
    tone: 'bg-amber-500/10 text-amber-700 ring-amber-500/15',
  },
  {
    name: 'wiki',
    label: 'Knowledge Base',
    icon: BookOpen,
    desc: 'Team wiki & documentation',
    href: '/kb',
    tone: 'bg-indigo-500/10 text-indigo-600 ring-indigo-500/15',
  },
]

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { user } = useAuthStore()

  const startAnalysis = (prompt: string) => {
    // Navigate to chat — ChatInput will handle the first message
    navigate('/chat/agent', { state: { initialPrompt: prompt } })
  }

  const handleFileAndGo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    navigate('/chat/agent', { state: { uploadFile: file } })
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-rose-500/5" />
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
          <div className="mb-5">
            <BrandLogo size="lg" className="mb-4" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
              {t('home.title')}
            </h1>
          </div>
          <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mb-8 leading-relaxed">
            {t('home.subtitle')}
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => navigate('/chat/agent')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors shadow-lg shadow-primary/25"
            >
              <Sparkles className="w-4 h-4" />
              {t('home.startChat')}
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-card border border-border text-sm font-medium hover:bg-secondary transition-colors"
            >
              <Upload className="w-4 h-4" />
              {t('home.uploadProtein')}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileAndGo}
              className="hidden"
              accept=".pdb,.fasta,.cif,.sdf,.txt,.csv,.json"
            />
          </div>

          {/* Stats */}
          <div className="flex flex-wrap gap-6 mt-10">
            {[
              { value: '25', label: t('home.toolsAvailable') },
              { value: '8', label: t('home.toolCategories') },
              { value: '6', label: t('home.agentStages') },
            ].map((stat) => (
              <div key={stat.label}>
                <span className="text-2xl font-bold text-foreground">{stat.value}</span>
                <span className="text-sm text-muted-foreground ml-2">{stat.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Quick Analyses */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">{t('home.quickAnalyses')}</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {QUICK_ANALYSES.map((item) => {
            const Icon = item.icon
            const prompt = t(item.promptKey)
            return (
              <button
                key={item.titleKey}
                onClick={() => startAnalysis(prompt)}
                className={`group text-left p-4 rounded-xl border transition-all cursor-pointer ${item.color}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${item.color.split(' ')[0]} ${item.color.split(' ')[1]}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium mb-0.5">{t(item.titleKey)}</h3>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {prompt}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-2" />
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {user?.role === 'admin' && (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-10">
          <div className="rounded-3xl border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-slate-50 p-6 sm:p-7">
            <div className="flex flex-wrap items-center justify-between gap-5">
              <div className="flex items-start gap-4">
                <div className="rounded-2xl bg-emerald-100 p-3 text-emerald-700">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-foreground">管理后台</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
                    管理用户角色、查看任务审计，并导出脱敏审计 CSV。
                  </p>
                </div>
              </div>
              <button
                onClick={() => navigate('/admin')}
                className="inline-flex items-center gap-2 rounded-2xl bg-emerald-700 px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-emerald-800"
              >
                进入后台
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Tool Categories */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <div className="rounded-3xl border border-border bg-card/70 p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold tracking-tight">
                {t('home.toolCategoriesTitle')}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Jump into the part of the platform you need most.
              </p>
            </div>
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              {TOOL_CATEGORIES.length} modules
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {TOOL_CATEGORIES.map((cat) => {
            const Icon = cat.icon
            return (
              <button
                key={cat.name}
                type="button"
                className="group flex min-h-28 items-start gap-3 rounded-2xl border border-border bg-background/80 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-ring/50 hover:bg-background hover:shadow-md"
                onClick={() => (cat.href ? navigate(cat.href) : navigate('/chat/agent'))}
              >
                <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ${cat.tone}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-foreground">{cat.label}</h3>
                    <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <p className="mt-1.5 max-w-[18ch] text-xs leading-5 text-muted-foreground">
                    {cat.desc}
                  </p>
                </div>
              </button>
            )
          })}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 text-center">
        <p className="text-xs text-muted-foreground">
          Protein AI Platform — {t('home.footer')}
        </p>
      </footer>
    </div>
  )
}
