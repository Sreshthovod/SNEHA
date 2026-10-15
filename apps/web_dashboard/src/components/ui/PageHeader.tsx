import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  lede?: ReactNode
}

export function PageHeader({ title, lede }: PageHeaderProps) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {lede && <p className="page-header__lede">{lede}</p>}
    </header>
  )
}
