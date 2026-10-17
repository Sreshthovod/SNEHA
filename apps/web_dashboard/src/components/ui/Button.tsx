import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'danger-outline' | 'ghost'
  pending?: boolean
}

export function Button({
  variant = 'primary',
  className,
  type = 'button',
  pending = false,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const classes = ['button', variant !== 'primary' && `button--${variant}`, className]
    .filter(Boolean)
    .join(' ')
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      {...rest}
    >
      {pending ? 'Please wait…' : children}
    </button>
  )
}
