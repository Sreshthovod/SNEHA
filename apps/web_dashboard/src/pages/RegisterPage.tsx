import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { register } from '../api/auth'
import { ApiError } from '../api/client'
import type { RegisterRequest } from '../api/types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SelectField, TextField } from '../components/ui/Field'
import { Notice } from '../components/ui/States'
import { ResendVerification } from './AccountEmailPages'

type Role = RegisterRequest['role']

export function RegisterPage() {
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'caregiver' as Role })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [done, setDone] = useState<{ role: Role; email: string } | null>(null)
  const [pending, setPending] = useState(false)

  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (!form.full_name.trim()) next.full_name = 'Enter your name.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Enter a valid email address.'
    if (form.password.length < 12) next.password = 'Use at least 12 characters. A short sentence works well.'
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length) return
    setPending(true)
    try {
      await register({ ...form, email: form.email.trim(), full_name: form.full_name.trim() })
      setDone({ role: form.role, email: form.email.trim() })
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : 'Could not create the account.')
    } finally {
      setPending(false)
    }
  }

  if (done)
    return (
      <Card title="Account created">
        <Notice tone="info">
          We sent a link to <strong>{done.email}</strong>. Open it to confirm your email; it works
          once and expires in 2 days. Check your spam folder if you do not see it.
        </Notice>
        {done.role === 'clinician' ? (
          <p>
            Your clinician account needs to be verified by the SNEHA team before families can share
            records with you. You can sign in now; shared patients appear once verified and granted.
          </p>
        ) : (
          <p>After confirming your email, sign in and add the person you care for.</p>
        )}
        <Link to="/login" className="button">
          Go to sign in
        </Link>
        <details className="resend-details">
          <summary>No email after a few minutes?</summary>
          <ResendVerification email={done.email} />
        </details>
      </Card>
    )

  return (
    <Card title="Create an account" className="narrow">
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Your name" value={form.full_name} onChange={(e) => set('full_name')(e.target.value)} error={errors.full_name} required autoComplete="name" />
        <TextField label="Email" type="email" value={form.email} onChange={(e) => set('email')(e.target.value)} error={errors.email} required autoComplete="email" />
        <TextField
          label="Password"
          type="password"
          hint="At least 12 characters."
          value={form.password}
          onChange={(e) => set('password')(e.target.value)}
          error={errors.password}
          required
          autoComplete="new-password"
        />
        <SelectField
          label="I am a"
          value={form.role}
          onChange={(e) => set('role')(e.target.value)}
          options={[
            { value: 'caregiver', label: 'Family member or caregiver' },
            { value: 'clinician', label: 'Clinician (needs verification)' },
          ]}
        />
        {formError && <Notice tone="danger">{formError}</Notice>}
        <Button type="submit" pending={pending}>
          Create account
        </Button>
      </form>
      <p className="landing__alt">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </Card>
  )
}
