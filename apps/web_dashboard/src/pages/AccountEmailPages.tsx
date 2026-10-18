import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { forgotPassword, resendVerification, resetPassword, verifyEmail } from '../api/auth'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { TextField } from '../components/ui/Field'
import { Notice } from '../components/ui/States'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Read the one-time token from the link once, then remove it from the address bar so it
 * is not kept in history or sent onwards.
 */
function useLinkToken(): string {
  const [params] = useSearchParams()
  const [token] = useState(() => params.get('token') ?? '')
  useEffect(() => {
    if (window.location.search) window.history.replaceState(null, '', window.location.pathname)
  }, [])
  return token
}

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

/** Ask for a new confirmation link. Used on the login page and after registering. */
export function ResendVerification({ email: initial = '' }: { email?: string }) {
  const [email, setEmail] = useState(initial)
  const [state, setState] = useState<'idle' | 'pending' | 'sent' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!EMAIL_RE.test(email.trim())) {
      setError('Enter your email address, like name@example.org.')
      return
    }
    setError(null)
    setState('pending')
    try {
      await resendVerification(email.trim())
      setState('sent')
    } catch (e) {
      setError(message(e, 'Could not send the link. Please try again.'))
      setState('error')
    }
  }

  if (state === 'sent')
    return (
      <Notice tone="success">
        If that address has an account waiting for confirmation, a new link is on its way. Check
        your inbox and spam folder.
      </Notice>
    )
  return (
    <form onSubmit={onSubmit} noValidate className="resend-form">
      <TextField
        label="Email for the new link"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={error ?? undefined}
      />
      <Button type="submit" variant="secondary" pending={state === 'pending'}>
        Send a new confirmation link
      </Button>
    </form>
  )
}

export function VerifyEmailPage() {
  const token = useLinkToken()
  const [state, setState] = useState<'pending' | 'done' | 'failed'>(token ? 'pending' : 'failed')
  const [error, setError] = useState<string | null>(
    token ? null : 'This link is incomplete. Open the link from the email again.',
  )
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    verifyEmail(token)
      .then(() => setState('done'))
      .catch((e: unknown) => {
        setError(message(e, 'Could not confirm your email. Please try again.'))
        setState('failed')
      })
  }, [token])

  return (
    <Card title="Confirm your email" className="narrow">
      {state === 'pending' && <p role="status">Confirming your email…</p>}
      {state === 'done' && (
        <>
          <Notice tone="success">Thank you. Your email is confirmed.</Notice>
          <Link to="/login" className="button">
            Go to sign in
          </Link>
        </>
      )}
      {state === 'failed' && (
        <>
          <Notice tone="danger">{error}</Notice>
          <ResendVerification />
        </>
      )}
    </Card>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!EMAIL_RE.test(email.trim())) {
      setError('Enter your email address, like name@example.org.')
      return
    }
    setError(null)
    setPending(true)
    try {
      await forgotPassword(email.trim())
      setSent(true)
    } catch (e) {
      setError(message(e, 'Could not send the link. Please try again.'))
    } finally {
      setPending(false)
    }
  }

  return (
    <Card title="Forgot your password?" className="narrow">
      {sent ? (
        <>
          <Notice tone="success">
            If an account uses {email.trim()}, we have sent a link to choose a new password. It
            works once and expires soon. Check your spam folder too.
          </Notice>
          <Link to="/login" className="button button--secondary">
            Back to sign in
          </Link>
        </>
      ) : (
        <form onSubmit={onSubmit} noValidate>
          <p>Enter the email you sign in with. We will send you a link to choose a new password.</p>
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={error ?? undefined}
            required
          />
          <Button type="submit" pending={pending}>
            Send reset link
          </Button>
          <p className="landing__alt">
            Remembered it? <Link to="/login">Sign in</Link>
          </p>
        </form>
      )}
    </Card>
  )
}

export function ResetPasswordPage() {
  const token = useLinkToken()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})
  const [formError, setFormError] = useState<string | null>(
    token ? null : 'This link is incomplete. Open the link from the email again.',
  )
  const [pending, setPending] = useState(false)
  const [done, setDone] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: typeof errors = {}
    if (password.length < 12) next.password = 'Use at least 12 characters. A short sentence works well.'
    if (confirm !== password) next.confirm = 'The two passwords are different.'
    setErrors(next)
    if (Object.keys(next).length || !token) return
    setFormError(null)
    setPending(true)
    try {
      await resetPassword(token, password)
      setDone(true)
    } catch (e) {
      setFormError(message(e, 'Could not change the password. Please try again.'))
    } finally {
      setPending(false)
    }
  }

  if (done)
    return (
      <Card title="Password changed" className="narrow">
        <Notice tone="success">
          Your new password is saved. For your safety you have been signed out on every device.
        </Notice>
        <Link to="/login" className="button">
          Sign in
        </Link>
      </Card>
    )

  return (
    <Card title="Choose a new password" className="narrow">
      <form onSubmit={onSubmit} noValidate>
        <TextField
          label="New password"
          type="password"
          hint="At least 12 characters."
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
          required
        />
        <TextField
          label="New password again"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={errors.confirm}
          required
        />
        {formError && (
          <Notice tone="danger">
            {formError} <Link to="/forgot-password">Ask for a new link</Link>
          </Notice>
        )}
        <Button type="submit" pending={pending} disabled={!token}>
          Save new password
        </Button>
      </form>
    </Card>
  )
}
