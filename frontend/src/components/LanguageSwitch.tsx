import { useTranslation } from 'react-i18next'
import { Languages } from 'lucide-react'

export function LanguageSwitch() {
  const { i18n } = useTranslation()

  const toggleLanguage = () => {
    const next = i18n.language === 'en' ? 'zh' : 'en'
    i18n.changeLanguage(next)
  }

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-1 px-2 py-1.5 rounded-md hover:bg-secondary text-xs font-medium text-muted-foreground transition-colors"
      title={i18n.language === 'en' ? 'Switch to Chinese' : '切换到英文'}
    >
      <Languages className="w-4 h-4" />
      <span className="hidden sm:inline">{i18n.language === 'en' ? 'EN' : '中文'}</span>
    </button>
  )
}
