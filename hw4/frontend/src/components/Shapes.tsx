// Pure-CSS Memphis-style confetti shapes used as decoration (no image assets).
export default function Shapes({ variant = 'hero' }: { variant?: 'hero' | 'band' }) {
  return (
    <div className={`shapes shapes--${variant}`} aria-hidden="true">
      <span className="shape shape--circle" />
      <span className="shape shape--tri" />
      <span className="shape shape--squiggle" />
      <span className="shape shape--dots" />
      <span className="shape shape--ring" />
      <span className="shape shape--bar" />
    </div>
  )
}
