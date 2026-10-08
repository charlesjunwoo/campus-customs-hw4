import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { isSpooky } from '../season'
import { spook } from '../spook'

const MAIN_LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  async function onLogout() {
    close()
    await logout()
    navigate('/')
  }

  return (
    <header className="nav">
      <div className="nav__inner">
        <Link to="/" className="logo" onClick={close} aria-label="Campus Customs home">
          <span className="logo__mark" aria-hidden="true">
            <span className="logo__tri" />
            <span className="logo__dot" />
          </span>
          <span className="logo__text">
            Campus<em>Customs</em>
          </span>
        </Link>

        <button
          className="nav__toggle"
          aria-expanded={open}
          aria-controls="nav-links"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? 'Close' : 'Menu'}
        </button>

        <nav id="nav-links" className={`nav__links ${open ? 'is-open' : ''}`} aria-label="Main">
          {MAIN_LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className="nav__link" onClick={close}>
              {l.label}
            </NavLink>
          ))}
          <span className="nav__spacer" />
          {isSpooky() && (
            <button className="nav__spook" onClick={() => spook('full')} title="Trick or treat!" aria-label="Trick or treat">
              🎃
            </button>
          )}
          {user ? (
            <>
              <span className="nav__hello" title={user.email}>
                Hi, {user.first_name}!
              </span>
              <button className="btn btn--ghost btn--sm" onClick={onLogout}>
                Log Out
              </button>
            </>
          ) : (
            <span className={`nav__auth ${loading ? 'is-loading' : ''}`}>
              <NavLink to="/login" className="nav__link" onClick={close}>
                Log In
              </NavLink>
              <NavLink to="/create-account" className="btn btn--pink btn--sm" onClick={close}>
                Create Account
              </NavLink>
            </span>
          )}
        </nav>
      </div>
    </header>
  )
}
