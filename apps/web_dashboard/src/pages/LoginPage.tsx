import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { TextField } from '../components/ui/Field'
import { Notice } from '../components/ui/States'
import { homePathFor, useAuth } from '../state/auth'
import { useSettings } from '../state/settings'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Landing page and sign-in form. */
export function LoginPage() {
  const { state, signIn } = useAuth()
  const { t } = useSettings()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  if (state.status === 'signed_in') return <Navigate to={homePathFor(state.user)} replace />

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: typeof errors = {}
    if (!EMAIL_RE.test(email.trim())) next.email = 'Enter your email address, like name@example.org.'
    if (!password) next.password = 'Enter your password.'
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length) return
    setPending(true)
    try {
      const user = await signIn({ email: email.trim(), password })
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from.startsWith('/app') ? from : homePathFor(user), { replace: true })
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : 'Sign-in failed. Please try again.',
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="landing">
      <section className="landing__intro">
        <p className="eyebrow">{t('app.name')}</p>
        <h1>{t('app.tagline')}</h1>
        <ul className="landing__points">
          <li>Curate a personal Memory Bank of familiar people, places and stories.</li>
          <li>See gentle activity summaries from the phone app.</li>
          <li>Share reports with a clinician only when you choose to.</li>
        </ul>
        <p className="field__hint">
          SNEHA supports daily activities and memory. It does not diagnose any condition.
        </p>
      </section>
      <Card title={t('login.title')} className="landing__form">
        <form onSubmit={onSubmit} noValidate>
          <TextField
            label={t('login.email')}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            required
          />
          <TextField
            label={t('login.password')}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            required
          />
          {formError && <Notice tone="danger">{formError}</Notice>}
          <Button type="submit" pending={pending} className="button--block">
            {t('login.submit')}
          </Button>
        </form>
        <p className="landing__alt">
          {t('login.noAccount')} <Link to="/register">{t('login.register')}</Link>
        </p>
      </Card>
    </div>
  )
}
