import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="section center">
      <p className="big-404">404</p>
      <h1 className="h2">This page went to Harvard.</h1>
      <p className="muted">Let's get you back somewhere better.</p>
      <Link to="/" className="btn btn--pink">
        Back home
      </Link>
    </div>
  )
}
