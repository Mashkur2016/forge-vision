import type { ReactNode } from 'react'

interface AuthLayoutProps {
  children: ReactNode
}

const anton: React.CSSProperties = { fontFamily: "'Anton', sans-serif" }

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', height: '100vh', fontFamily: "'Source Sans 3', sans-serif", overflow: 'hidden' }}>

      {/* ── LEFT PANEL ── */}
      <div style={{
        background: '#FFCC00',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Decorative circles */}
        <div style={{
          position: 'absolute', bottom: '-120px', right: '-120px',
          width: '400px', height: '400px', borderRadius: '50%',
          background: 'rgba(0,0,0,0.06)',
        }} />
        <div style={{
          position: 'absolute', top: '-80px', left: '-80px',
          width: '280px', height: '280px', borderRadius: '50%',
          background: 'rgba(255,255,255,0.12)',
        }} />

        {/* Content */}
        <div style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
          {/* Logo */}
          <div style={{
            width: '180px', height: '180px',
            margin: '0 auto 2rem',
            borderRadius: '20px',
            overflow: 'hidden',
            boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
            background: 'white',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <img
              src="/logo1.jpg"
              alt="FORGE-Vision"
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
          </div>

          {/* Brand */}
          <div style={{ ...anton, fontSize: '3.6rem', letterSpacing: '0.04em', color: '#1a1a1a', lineHeight: 1, marginBottom: '0.5rem' }}>
            FORGE<br />VISION
          </div>

          {/* Gold rule */}
          <div style={{ width: '60px', height: '5px', background: '#1a1a1a', margin: '1.2rem auto', borderRadius: '3px' }} />

          {/* Tagline */}
          <div style={{ ...anton, fontSize: '1.05rem', letterSpacing: '0.18em', color: '#1a1a1a', opacity: 0.75, textTransform: 'uppercase' }}>
            AI Employee Training System
          </div>

          {/* Slogan */}
          <div style={{
            marginTop: '1rem',
            fontSize: '0.78rem',
            fontStyle: 'italic',
            color: 'rgba(0,0,0,0.55)',
            letterSpacing: '0.06em',
          }}>
            Research. Innovation. Transformation.
          </div>
        </div>

        {/* Footer */}
        <div style={{
          position: 'absolute', bottom: '2rem',
          fontSize: '0.78rem', color: 'rgba(0,0,0,0.45)',
          letterSpacing: '0.05em',
        }}>
          Research Project
        </div>
      </div>

      {/* ── RIGHT PANEL ── */}
      <div style={{
        background: '#FEFFFF',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 4rem',
        overflowY: 'auto',
        animation: 'authSlideIn 0.5s cubic-bezier(0.22,1,0.36,1) both',
      }}>
        <style>{`
          @keyframes authSlideIn {
            from { opacity: 0; transform: translateX(30px); }
            to   { opacity: 1; transform: translateX(0); }
          }
        `}</style>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          {children}
        </div>
      </div>
    </div>
  )
}
