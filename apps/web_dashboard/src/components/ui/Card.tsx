import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  children: ReactNode
  /** Heading level for the title; keeps the document outline correct per page. */
  headingLevel?: 2 | 3
  actions?: ReactNode
  className?: string
}

export function Card({ title, children, headingLevel = 2, actions, className }: CardProps) {
  const Heading = headingLevel === 2 ? 'h2' : 'h3'
  return (
    <section className={['card', className].filter(Boolean).join(' ')} aria-label={title}>
      {(title || actions) && (
        <div className="card__header">
          {title && <Heading className="card__title">{title}</Heading>}
          {actions && <div className="card__actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}
