import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__squiggle" aria-hidden="true" />
      <div className="footer__inner">
        <div>
          <p className="footer__brand">
            Campus<em>Customs</em>
          </p>
          <p className="muted">Yale gear for the whole Bulldog family.</p>
        </div>
        <div>
          <p className="footer__head">Shop</p>
          <Link to="/products">All products</Link>
          <Link to="/products?category=Hoodies">Hoodies</Link>
          <Link to="/products?category=Crewnecks">Crewnecks</Link>
        </div>
        <div>
          <p className="footer__head">Visit</p>
          <p>57 Broadway</p>
          <p>New Haven, CT 06511</p>
        </div>
        <div>
          <p className="footer__head">Account</p>
          <Link to="/login">Log in</Link>
          <Link to="/create-account">Create account</Link>
          <Link to="/about">About us</Link>
        </div>
      </div>
      <p className="footer__fine">© {new Date().getFullYear()} Campus Customs · Class project demo store</p>
    </footer>
  )
}
