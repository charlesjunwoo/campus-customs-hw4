import { Link } from 'react-router-dom'
import Shapes from '../components/Shapes'

const VALUES = [
  {
    title: 'Licensed, not knock-off',
    body: 'Every Yale mark we print is officially licensed, so the bulldog on your chest is the real deal.',
  },
  {
    title: 'Something for every Eli',
    body: 'All fourteen residential colleges, the varsity teams, the graduate and professional schools, and gear for the folks cheering from the stands.',
  },
  {
    title: 'Built to be worn out',
    body: 'Heavyweight fleece, soft tri-blends, and classic cuts that survive dorm laundry and still look sharp at reunion.',
  },
]

export default function About() {
  return (
    <>
      <section className="hero hero--short">
        <Shapes />
        <div className="hero__inner">
          <p className="eyebrow">About us</p>
          <h1 className="hero__title">
            A neighborhood shop with a <span className="hl hl--teal">very</span> big mascot.
          </h1>
        </div>
      </section>

      <section className="section prose">
        <p className="lede">
          Campus Customs is the team behind Yale Bulldog Blue, a store dedicated to one simple idea: Yale pride
          should be comfortable, a little playful, and easy to find.
        </p>
        <p>
          Our shop sits on Broadway in New Haven, right where campus spills into the city. Our customers walk in
          with all kinds of missions: a first-year who needs a college crewneck before their first Saturday
          game, a parent hunting for a "Yale Dad" hoodie, a grad student who wants something that says School
          of Music instead of just "Yale." We stock for all of them.
        </p>
        <p>
          Our racks lean on the classics, like navy and heather gray, big block letters, left-chest wordmarks,
          and the occasional vintage bulldog. Then we fill in the details that make Yale feel like <em>your</em>{' '}
          Yale: crests for each residential college, a mark for each team, and pieces made for the whole
          family tree.
        </p>
      </section>

      <section className="band">
        <Shapes variant="band" />
        <div className="section">
          <h2 className="h2">
            What we <span className="hl hl--yellow">stand for</span>
          </h2>
          <div className="values">
            {VALUES.map((v, i) => (
              <div key={v.title} className={`value value--${i}`}>
                <span className="value__num">0{i + 1}</span>
                <h3 className="h3">{v.title}</h3>
                <p>{v.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section split">
        <div>
          <p className="eyebrow">Visit</p>
          <h2 className="h2">57 Broadway, New Haven, CT 06511</h2>
          <p>
            Pop in to try sizes, browse the full wall of crewnecks, or ask what just restocked. Shopping from
            afar? Our online assistant can check stock by size and point you to the right fit.
          </p>
          <div className="hero__cta">
            <Link to="/products" className="btn btn--pink">
              Browse products
            </Link>
            <Link to="/create-account" className="btn btn--ghost">
              Create an account
            </Link>
          </div>
        </div>
        <div className="split__art" aria-hidden="true">
          <div className="pennant">
            <span>YALE</span>
          </div>
        </div>
      </section>
    </>
  )
}
