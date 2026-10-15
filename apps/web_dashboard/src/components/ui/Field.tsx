import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

interface FieldShellProps {
  label: string
  hint?: ReactNode
  error?: string | null
  required?: boolean
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode
}

/** Label + control + hint + error, wired with aria-describedby / aria-invalid. */
export function FieldShell({ label, hint, error, required, children }: FieldShellProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  return (
    <div className={['field', error && 'field--error'].filter(Boolean).join(' ')}>
      <label htmlFor={id} className="field__label">
        {label}
        {required && <span className="field__required"> (required)</span>}
      </label>
      {hint && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
      {children({ id, describedBy, invalid: Boolean(error) })}
      {error && (
        <p id={errorId} className="field__error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

type Common = { label: string; hint?: ReactNode; error?: string | null }

export function TextField({ label, hint, error, required, ...rest }: Common & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <input
          id={id}
          className="input"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

export function TextArea({ label, hint, error, required, ...rest }: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <textarea
          id={id}
          className="input input--textarea"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

export interface Option {
  value: string
  label: string
}

export function SelectField({
  label,
  hint,
  error,
  required,
  options,
  ...rest
}: Common & SelectHTMLAttributes<HTMLSelectElement> & { options: Option[] }) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <select
          id={id}
          className="input"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  )
}

export function CheckboxField({ label, hint, ...rest }: { label: string; hint?: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <div className="field field--checkbox">
      <input id={id} type="checkbox" className="checkbox" aria-describedby={hint ? `${id}-hint` : undefined} {...rest} />
      <label htmlFor={id} className="field__label">
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="field__hint">
          {hint}
        </p>
      )}
    </div>
  )
}
