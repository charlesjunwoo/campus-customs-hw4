import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import AuthLayout from '../components/AuthLayout'
import SignedInNotice from '../components/SignedInNotice'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email.trim(), password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? '/', { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout kicker="Welcome back" title={<>Log <span className="hl hl--pink">in</span></>}>
      {user ? (
        <SignedInNotice />
      ) : (
        <>
          <form className="form" onSubmit={onSubmit} noValidate={false}>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && (
              <p className="notice notice--error" role="alert">
                {error}
              </p>
            )}
            <button type="submit" className="btn btn--pink btn--block" disabled={busy}>
              {busy ? 'Logging in…' : 'Log in'}
            </button>
          </form>
          <p className="muted auth__switch">
            New here? <Link to="/create-account">Create an account</Link>
          </p>
        </>
      )}
    </AuthLayout>
  )
}
