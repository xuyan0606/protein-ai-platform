import { useEffect } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import type { Toast as ToastType } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

const iconMap = {
  success: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  error: <XCircle className="w-4 h-4 text-red-500" />,
  info: <Info className="w-4 h-4 text-blue-500" />,
  warning: <AlertTriangle className="w-4 h-4 text-amber-500" />,
}

const bgMap = {
  success: 'border-green-500/30',
  error: 'border-red-500/30',
  info: 'border-blue-500/30',
  warning: 'border-amber-500/30',
}

function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useUIStore((s) => s.removeToast)

  useEffect(() => {
    const timer = setTimeout(() => {
      removeToast(toast.id)
    }, 5000)
    return () => clearTimeout(timer)
  }, [toast.id, removeToast])

  return (
    <div
      className={`pointer-events-auto bg-card border ${bgMap[toast.type]} rounded-lg shadow-lg px-4 py-3 flex items-start gap-3 min-w-[280px] max-w-[420px]`}
      style={{ animation: 'toast-slide-in 0.3s ease-out' }}
    >
      <span className="shrink-0 mt-0.5">{iconMap[toast.type]}</span>
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 p-0.5 rounded hover:bg-secondary text-muted-foreground"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts)

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  )
}
