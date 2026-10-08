import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCollections, getProducts } from '../api'
import ProductCard from '../components/ProductCard'
import Shapes from '../components/Shapes'
import { isSpooky } from '../season'
import type { Collection, ProductCard as Card } from '../types'

// Hand-picked spotlight: one strong piece from each corner of the shop.
const FEATURED_IDS = [
  'basic-hoodie-big-yale',
  'district-vit-crewneck-vintage-bulldog',
  '2025-yale-vs-harvard-t-shirt',
  'brooks-brothers-bomber-jacket-yale',
]

const COLLECTION_BLURBS: Record<string, string> = {
  'residential-colleges': 'Rep your college, from Benjamin Franklin to Trumbull.',
  athletics: 'Left-chest marks and gameday tees for every varsity squad.',
  family: 'Mom, Dad, Grandpa, Aunt: everyone in the family gets one.',
  'graduate-schools': 'Law, Art, Medicine, Music, Forestry, and more.',
}

export default function Home() {
  const [featured, setFeatured] = useState<Card[]>([])
  const [collections, setCollections] = useState<Collection[]>([])

  useEffect(() => {
    getProducts()
      .then((all) => {
        const picks = FEATURED_IDS.map((id) => all.find((p) => p.product_id === id)).filter(
          (p): p is Card => Boolean(p),
        )
        setFeatured(picks.length ? picks : all.slice(0, 4))
      })
      .catch(() => setFeatured([]))
    getCollections().then(setCollections).catch(() => setCollections([]))
  }, [])

  return (
    <>
      <section className="hero">
        <Shapes />
        <div className="hero__inner">
          <p className="eyebrow">{isSpooky() ? 'Spooky season at 57 Broadway' : 'New Haven · 57 Broadway'}</p>
          <h1 className="hero__title">
            Wear your <span className="hl hl--pink">Yale</span> out loud.
          </h1>
          <p className="hero__lede">
            Campus Customs makes the sweatshirts you live in for four years and keep for forty: hoodies,
            crewnecks, quarter-zips, and tees for students, alumni, and the whole Bulldog family.
          </p>
          <div className="hero__cta">
            <Link to="/products" className="btn btn--pink">
              Shop the collection
            </Link>
            <Link to="/about" className="btn btn--ghost">
              Our story
            </Link>
          </div>
        </div>
        <div className="hero__sticker" aria-hidden="true">
          <span>{isSpooky() ? 'Boo-la' : 'Boola'}</span>
          <span>Boola!</span>
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2 className="h2">
            Fresh <span className="hl hl--teal">favorites</span>
          </h2>
          <Link to="/products" className="link-arrow">
            See everything →
          </Link>
        </div>
        <div className="grid">
          {featured.map((p, i) => (
            <ProductCard key={p.product_id} product={p} index={i} />
          ))}
        </div>
      </section>

      <section className="band">
        <Shapes variant="band" />
        <div className="section">
          <h2 className="h2">
            Find your <span className="hl hl--yellow">corner</span> of Yale
          </h2>
          <div className="tiles">
            {collections.map((c, i) => (
              <Link key={c.slug} to={`/products?collection=${c.slug}`} className={`tile tile--${i % 4}`}>
                <span className="tile__count">{c.count}</span>
                <span className="tile__name">{c.name}</span>
                <span className="tile__blurb">{COLLECTION_BLURBS[c.slug]}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="section split">
        <div className="split__art" aria-hidden="true">
          <div className="storefront">
            <div className="storefront__awning" />
            <div className="storefront__sign">57 Broadway</div>
            <div className="storefront__windows">
              <span />
              <span />
            </div>
            <div className="storefront__door" />
          </div>
        </div>
        <div>
          <p className="eyebrow">Come say hi</p>
          <h2 className="h2">Try it on in person</h2>
          <p>
            Our shop sits at <strong>57 Broadway in New Haven</strong>, a short walk from Old Campus. Stop by
            between classes, before the game, or on move-in weekend when your parents suddenly need three
            hoodies each.
          </p>
          <p>
            Can't make it to Broadway? Ask our chat assistant (bottom right) about sizes, stock, and what
            pairs with what.
          </p>
        </div>
      </section>
    </>
  )
}
