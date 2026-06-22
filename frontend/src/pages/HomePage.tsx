import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import {
  Dna, Beaker, Zap, ArrowRight, Sparkles, Upload, FileText,
  Microscope, Thermometer, GitCompare, Scissors, ChevronRight,
} from 'lucide-react'
import { useRef } from 'react'

const QUICK_ANALYSES = [
  {
    icon: Microscope,
    titleKey: 'home.analyzeStability',
    color: 'bg-blue-500/10 text-blue-500 border-blue-500/20 hover:border-blue-500/40',
    prompt: 'Analyze this protein sequence for thermostability and pH stability.',
  },
  {
    icon: Thermometer,
    titleKey: 'home.designMutations',
    color: 'bg-amber-500/10 text-amber-500 border-amber-500/20 hover:border-amber-500/40',
    prompt: 'Design mutations to improve the thermostability of this enzyme. Scan for key positions and predict mutation effects.',
  },
  {
    icon: GitCompare,
    titleKey: 'home.benchmark',
    color: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20 hover:border-emerald-500/40',
    prompt: 'Benchmark this protein against known families (GH13, GH11, GH7, GH5, GH1). Analyze conserved motifs and classify.',
  },
  {
    icon: Scissors,
    titleKey: 'home.docking',
    color: 'bg-purple-500/10 text-purple-500 border-purple-500/20 hover:border-purple-500/40',
    prompt: 'Perform molecular docking analysis for this protein with its substrate.',
  },
  {
    icon: Dna,
    titleKey: 'home.predictStructure',
    color: 'bg-rose-500/10 text-rose-500 border-rose-500/20 hover:border-rose-500/40',
    prompt: 'Predict the 3D structure from this protein sequence using ESMFold.',
  },
  {
    icon: Beaker,
    titleKey: 'home.solubility',
    color: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20 hover:border-cyan-500/40',
    prompt: 'Scan mutations to improve protein solubility and expression levels.',
  },
]

const TOOL_CATEGORIES = [
  { name: 'design', label: 'Protein Design', icon: Beaker, desc: 'Sequence & structure design tools' },
  { name: 'prediction', label: 'Prediction', icon: Zap, desc: 'Structure & property prediction' },
  { name: 'simulation', label: 'Simulation', icon: Microscope, desc: 'MD & dynamics simulation' },
  { name: 'search', label: 'Search', icon: GitCompare, desc: 'Sequence & database search' },
  { name: 'engineering', label: 'Engineering', icon: Thermometer, desc: 'Mutation & optimization' },
  { name: 'docking', label: 'Docking', icon: Scissors, desc: 'Molecular docking tools' },
  { name: 'analysis', label: 'Analysis', icon: Sparkles, desc: 'Data analysis & scoring' },
]

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { user } = useAuthStore()
  const { newConversation, addMessage, syncNewConversation } = useChatStore()

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
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Dna className="w-5 h-5 text-primary" />
            </div>
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
            return (
              <button
                key={item.titleKey}
                onClick={() => startAnalysis(item.prompt)}
                className={`group text-left p-4 rounded-xl border transition-all cursor-pointer ${item.color}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${item.color.split(' ')[0]} ${item.color.split(' ')[1]}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium mb-0.5">{t(item.titleKey)}</h3>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {item.prompt}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-2" />
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* Tool Categories */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <h2 className="text-base font-semibold mb-5">{t('home.toolCategoriesTitle')}</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {TOOL_CATEGORIES.map((cat) => {
            const Icon = cat.icon
            return (
              <div
                key={cat.name}
                className="p-3.5 rounded-xl bg-card border border-border hover:border-ring/50 transition-colors cursor-pointer"
                onClick={() => navigate('/chat/agent')}
              >
                <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center mb-2.5">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                </div>
                <h3 className="text-sm font-medium capitalize mb-0.5">{cat.label}</h3>
                <p className="text-xs text-muted-foreground">{cat.desc}</p>
              </div>
            )
          })}
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
