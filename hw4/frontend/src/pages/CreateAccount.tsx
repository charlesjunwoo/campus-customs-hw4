import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import AuthLayout from '../components/AuthLayout'
import SignedInNotice from '../components/SignedInNotice'

const EMPTY = { firstName: '', lastName: '', email: '', password: '', confirm: '' }
const MIN_PASSWORD = 8

export default function CreateAccount() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (key: keyof typeof EMPTY) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const firstName = form.firstName.trim()
    const lastName = form.lastName.trim()
    const email = form.email.trim()
    if (!firstName || !lastName || !email || !form.password) return setError('All fields are required.')
    if (form.password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
    if (form.password !== form.confirm) return setError('Passwords do not match.')
    setError(null)
    setBusy(true)
    try {
      await register({ first_name: firstName, last_name: lastName, email, password: form.password })
      navigate('/', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout kicker="Join the pack" title={<>Create <span className="hl hl--teal">account</span></>}>
      {user ? (
        <SignedInNotice />
      ) : (
        <>
          <form className="form" onSubmit={onSubmit}>
            <div className="form__row">
              <label className="field">
                <span>First name</span>
                <input name="firstName" autoComplete="given-name" required maxLength={60} value={form.firstName} onChange={set('firstName')} />
              </label>
              <label className="field">
                <span>Last name</span>
                <input name="lastName" autoComplete="family-name" required maxLength={60} value={form.lastName} onChange={set('lastName')} />
              </label>
            </div>
            <label className="field">
              <span>Email</span>
              <input name="email" type="email" autoComplete="email" required value={form.email} onChange={set('email')} />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={MIN_PASSWORD}
                maxLength={128}
                value={form.password}
                onChange={set('password')}
              />
              <small className="field__hint">At least {MIN_PASSWORD} characters.</small>
            </label>
            <label className="field">
              <span>Confirm password</span>
              <input
                name="confirm"
                type="password"
                autoComplete="new-password"
                required
                maxLength={128}
                value={form.confirm}
                onChange={set('confirm')}
              />
            </label>
            {error && (
              <p className="notice notice--error" role="alert">
                {error}
              </p>
            )}
            <button type="submit" className="btn btn--pink btn--block" disabled={busy}>
              {busy ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          <p className="muted auth__switch">
            Already have one? <Link to="/login">Log in</Link>
          </p>
        </>
      )}
    </AuthLayout>
  )
}
