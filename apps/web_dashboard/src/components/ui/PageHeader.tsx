import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  lede?: ReactNode
  eyebrow?: string
  /** Page-level actions, right-aligned on desktop and full-width on phones. */
  actions?: ReactNode
}

export function PageHeader({ title, lede, eyebrow, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {lede && <p className="page-header__lede">{lede}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}
