import { useId } from 'react'
import { Button } from './Button'

/** A button that is unavailable, with the reason always visible and announced. */
export function DisabledWithReason({ label, reason }: { label: string; reason: string }) {
  const id = useId()
  return (
    <div className="disabled-reason">
      <Button variant="secondary" disabled aria-describedby={id}>
        {label}
      </Button>
      <p id={id} className="field__hint">
        {reason}
      </p>
    </div>
  )
}
