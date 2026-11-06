import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import AuthLayout from '@/components/AuthLayout'
import { useLogin } from '@/hooks/useAuth'

const anton: React.CSSProperties = { fontFamily: "'Anton', sans-serif" }

export default function Login() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [searchParams]          = useSearchParams()
  const login                   = useLogin()

  const successMessage = searchParams.get('registered')
    ? 'Account created — please sign in.'
    : searchParams.get('message') === 'password_reset'
      ? 'Password reset successfully — please sign in.'
      : null

  const errorMessage =
    login.error && 'response' in (login.error as object)
      ? ((login.error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
          'Sign in failed — please try again.')
      : login.isError
        ? 'Sign in failed — please try again.'
        : null

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    login.mutate({ email, password })
  }

  return (
    <AuthLayout>
      {/* Form header */}
      <div style={{ marginBottom: '2.5rem' }}>
        <div style={{ ...anton, fontSize: '2.4rem', color: '#1a1a1a', letterSpacing: '0.03em' }}>
          SIGN IN
        </div>
        <div style={{ display: 'block', width: '48px', height: '4px', background: '#FFCC00', margin: '0.9rem 0 0.7rem', borderRadius: '2px' }} />
        <div style={{ fontSize: '0.95rem', color: '#6b6b6b', fontWeight: 300 }}>
          Welcome back. Enter your credentials to continue.
        </div>
      </div>

      {/* Success banner */}
      {successMessage && (
        <div style={{
          background: '#f0fdf4', border: '1.5px solid #bbf7d0',
          color: '#166534', borderRadius: '8px',
          padding: '0.75rem 1rem', fontSize: '0.88rem', marginBottom: '1.2rem',
        }}>
          {successMessage}
        </div>
      )}

      {/* Error banner */}
      {errorMessage && (
        <div style={{
          background: '#fff5f5', border: '1.5px solid #f5c2c2',
          color: '#d32f2f', borderRadius: '8px',
          padding: '0.75rem 1rem', fontSize: '0.88rem', marginBottom: '1.2rem',
        }}>
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Email */}
        <div style={{ marginBottom: '1.4rem' }}>
          <label style={labelStyle}>Email Address</label>
          <div style={{ position: 'relative' }}>
            <span style={iconStyle}>✉</span>
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={inputStyle}
              onFocus={(e) => { e.currentTarget.style.borderColor = '#FFCC00' }}
              onBlur={(e)  => { e.currentTarget.style.borderColor = '#e8e8e8' }}
            />
          </div>
        </div>

        {/* Password */}
        <div style={{ marginBottom: '1.4rem' }}>
          <label style={labelStyle}>Password</label>
          <div style={{ position: 'relative' }}>
            <span style={iconStyle}>🔑</span>
            <input
              type={showPw ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={{ ...inputStyle, paddingRight: '2.8rem' }}
              onFocus={(e) => { e.currentTarget.style.borderColor = '#FFCC00' }}
              onBlur={(e)  => { e.currentTarget.style.borderColor = '#e8e8e8' }}
            />
            <button
              type="button"
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? 'Hide password' : 'Show password'}
              style={toggleBtnStyle}
            >
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {/* Remember + forgot */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.6rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.88rem', color: '#6b6b6b', cursor: 'pointer', fontWeight: 400 }}>
            <input type="checkbox" style={{ width: '16px', height: '16px', accentColor: '#FFCC00' }} />
            Remember me
          </label>
          <Link to="/forgot-password" style={{ fontSize: '0.88rem', color: '#1a1a1a', fontWeight: 600, textDecoration: 'none', borderBottom: '2px solid #FFCC00', paddingBottom: '1px' }}>
            Forgot password?
          </Link>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={login.isPending}
          style={submitBtnStyle}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#E6B800' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#FFCC00' }}
        >
          {login.isPending ? 'Signing in…' : 'SIGN IN →'}
        </button>
      </form>

      {/* Divider */}
      <div style={{ textAlign: 'center', margin: '1.6rem 0 1.2rem', position: 'relative', fontSize: '0.78rem', color: '#ccc', letterSpacing: '0.08em' }}>
        <span style={{ position: 'relative', zIndex: 1, background: '#FEFFFF', padding: '0 0.6rem' }}>OR</span>
        <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: '1px', background: '#e8e8e8' }} />
      </div>

      <p style={{ textAlign: 'center', fontSize: '0.9rem', color: '#6b6b6b' }}>
        Don&apos;t have an account?{' '}
        <Link to="/register" style={{ color: '#1a1a1a', fontWeight: 700, textDecoration: 'none', borderBottom: '2px solid #FFCC00', paddingBottom: '1px' }}>
          Register here
        </Link>
      </p>

      <p style={{ textAlign: 'center', fontSize: '0.75rem', color: '#bbb', marginTop: '1.2rem', letterSpacing: '0.04em' }}>
        🔒 Secured · GDPR Compliant · AES-256 Encrypted
      </p>

      <p style={{ textAlign: 'center', fontSize: '0.78rem', color: '#bbb', marginTop: '0.6rem' }}>
        <Link
          to="/setup"
          style={{ color: '#bbb', textDecoration: 'none', borderBottom: '1px dashed #ddd' }}
        >
          ⚙ Re-run Setup Wizard
        </Link>
      </p>
    </AuthLayout>
  )
}

// ── Shared micro-styles ──────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.78rem',
  fontWeight: 700,
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  color: '#1a1a1a',
  marginBottom: '0.5rem',
}

const iconStyle: React.CSSProperties = {
  position: 'absolute',
  left: '14px',
  top: '50%',
  transform: 'translateY(-50%)',
  color: '#6b6b6b',
  fontSize: '1rem',
  pointerEvents: 'none',
}

const inputStyle: React.CSSProperties = {
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
}

const toggleBtnStyle: React.CSSProperties = {
  position: 'absolute',
  right: '12px',
  top: '50%',
  transform: 'translateY(-50%)',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: '#6b6b6b',
  display: 'flex',
  alignItems: 'center',
  padding: '4px',
}

const submitBtnStyle: React.CSSProperties = {
  width: '100%',
  padding: '1rem',
  background: '#FFCC00',
  color: '#1a1a1a',
  fontFamily: "'Anton', sans-serif",
  fontSize: '1.1rem',
  letterSpacing: '0.1em',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  transition: 'background 0.2s',
}
