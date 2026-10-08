import { Link } from 'react-router-dom'
import { useAuth } from '../auth'

export default function SignedInNotice() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <div className="form">
      <p className="notice" role="status">
        You're signed in as <strong>{user.name}</strong> ({user.email}).
      </p>
      <Link to="/products" className="btn btn--pink btn--block">
        Start shopping
      </Link>
      <button className="btn btn--block" onClick={() => logout()}>
        Log out
      </button>
    </div>
  )
}
