import type { ReactNode } from 'react'
import Shapes from './Shapes'

export default function AuthLayout({ title, kicker, children }: { title: ReactNode; kicker: string; children: ReactNode }) {
  return (
    <div className="auth">
      <Shapes variant="band" />
      <div className="auth__card">
        <p className="eyebrow">{kicker}</p>
        <h1 className="h1">{title}</h1>
        {children}
      </div>
    </div>
  )
}
