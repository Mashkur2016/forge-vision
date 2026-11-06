import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mail } from 'lucide-react'
import AuthLayout from '@/components/AuthLayout'
import { useForgotPassword } from '@/hooks/useAuth'

const anton: React.CSSProperties = { fontFamily: "'Anton', sans-serif" }

export default function ForgotPassword() {
  const [email, setEmail]  = useState('')
  const forgotPassword     = useForgotPassword()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    forgotPassword.mutate({ email })
  }

  return (
    <AuthLayout>
      {/* Header */}
      <div style={{ marginBottom: '2.5rem' }}>
        <div style={{ ...anton, fontSize: '2.2rem', color: '#1a1a1a', letterSpacing: '0.03em' }}>
          RESET PASSWORD
        </div>
        <div style={{ display: 'block', width: '48px', height: '4px', background: '#FFCC00', margin: '0.9rem 0 0.7rem', borderRadius: '2px' }} />
        <div style={{ fontSize: '0.95rem', color: '#6b6b6b', fontWeight: 300 }}>
          Enter your email and we&apos;ll send a reset link.
        </div>
      </div>

      {forgotPassword.isSuccess ? (
        /* ── Success state ── */
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '72px', height: '72px',
            background: '#f0fdf4', borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 1.5rem',
          }}>
            <Mail size={32} color="#16a34a" />
          </div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: '#1a1a1a', marginBottom: '0.5rem' }}>
            Check your inbox
          </p>
          <p style={{ fontSize: '0.85rem', color: '#6b6b6b', marginBottom: '0.3rem' }}>
            Link expires in 30 minutes.
          </p>
          <p style={{ fontSize: '0.82rem', color: '#aaa', marginBottom: '2rem' }}>
            If that email is registered, you&apos;ll receive a reset link shortly.
          </p>
          <Link
            to="/login"
            style={{ fontSize: '0.9rem', color: '#1a1a1a', fontWeight: 700, textDecoration: 'none', borderBottom: '2px solid #FFCC00', paddingBottom: '1px' }}
          >
            ← Back to Sign In
          </Link>
        </div>
      ) : (
        /* ── Form state ── */
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.4rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#1a1a1a', marginBottom: '0.5rem' }}>
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#6b6b6b', fontSize: '1rem', pointerEvents: 'none' }}>
                ✉
              </span>
              <input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '0.85rem 1rem 0.85rem 2.6rem',
                  border: '2px solid #e8e8e8',
                  borderRadius: '8px',
                  fontFamily: "'Source Sans 3', sans-serif",
                  fontSize: '0.97rem',
                  color: '#1a1a1a',
                  background: '#FEFFFF',
                  outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = '#FFCC00' }}
                onBlur={(e)  => { e.currentTarget.style.borderColor = '#e8e8e8' }}
              />
            </div>
          </div>

          {forgotPassword.isError && (
            <div style={{ background: '#fff5f5', border: '1.5px solid #f5c2c2', color: '#d32f2f', borderRadius: '8px', padding: '0.75rem 1rem', fontSize: '0.88rem', marginBottom: '1.2rem' }}>
              Something went wrong — please try again.
            </div>
          )}

          <button
            type="submit"
            disabled={forgotPassword.isPending}
            style={{
              width: '100%', padding: '1rem',
              background: '#FFCC00', color: '#1a1a1a',
              fontFamily: "'Anton', sans-serif", fontSize: '1.05rem',
              letterSpacing: '0.1em', border: 'none', borderRadius: '8px',
              cursor: forgotPassword.isPending ? 'not-allowed' : 'pointer',
              opacity: forgotPassword.isPending ? 0.7 : 1,
              transition: 'background 0.2s',
              marginBottom: '1.2rem',
            }}
            onMouseEnter={(e) => { if (!forgotPassword.isPending) e.currentTarget.style.background = '#E6B800' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#FFCC00' }}
          >
            {forgotPassword.isPending ? 'Sending…' : 'SEND RESET LINK →'}
          </button>

          <div style={{ textAlign: 'center' }}>
            <Link
              to="/login"
              style={{ fontSize: '0.9rem', color: '#1a1a1a', fontWeight: 600, textDecoration: 'none', borderBottom: '2px solid #FFCC00', paddingBottom: '1px' }}
            >
              ← Back to Sign In
            </Link>
          </div>
        </form>
      )}

      <p style={{ textAlign: 'center', fontSize: '0.75rem', color: '#bbb', marginTop: '2.5rem', letterSpacing: '0.04em' }}>
        🔒 Secured · GDPR Compliant · AES-256 Encrypted
      </p>
    </AuthLayout>
  )
}
