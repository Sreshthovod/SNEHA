import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem {
  id: string
  label: string
  content: ReactNode
}

interface TabsProps {
  label: string
  items: TabItem[]
  selected: string
  onSelect: (id: string) => void
}

/** WAI-ARIA tabs: arrow keys move between tabs, Home/End jump to the ends. */
export function Tabs({ label, items, selected, onSelect }: TabsProps) {
  const baseId = useId()
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | null = null
    if (event.key === 'ArrowRight') next = (index + 1) % items.length
    if (event.key === 'ArrowLeft') next = (index - 1 + items.length) % items.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = items.length - 1
    if (next === null) return
    event.preventDefault()
    const item = items[next]
    onSelect(item.id)
    refs.current[item.id]?.focus()
  }

  const current = items.find((i) => i.id === selected) ?? items[0]
  return (
    <div className="tabs">
      <div role="tablist" aria-label={label} className="tabs__list">
        {items.map((item, index) => {
          const active = item.id === current.id
          return (
            <button
              key={item.id}
              ref={(el) => {
                refs.current[item.id] = el
              }}
              role="tab"
              type="button"
              id={`${baseId}-tab-${item.id}`}
              aria-selected={active}
              aria-controls={`${baseId}-panel-${item.id}`}
              tabIndex={active ? 0 : -1}
              className="tabs__tab"
              onClick={() => onSelect(item.id)}
              onKeyDown={(e) => onKeyDown(e, index)}
            >
              {item.label}
            </button>
          )
        })}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${current.id}`}
        aria-labelledby={`${baseId}-tab-${current.id}`}
        tabIndex={0}
        className="tabs__panel"
      >
        {current.content}
      </div>
    </div>
  )
}
