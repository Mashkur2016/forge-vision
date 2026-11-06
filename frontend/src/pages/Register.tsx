import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import AuthLayout from '@/components/AuthLayout'
import { useRegister } from '@/hooks/useAuth'

// ── Password strength ──────────────────────────────────────────────────────

function getStrength(pw: string) {
  let s = 0
  if (pw.length >= 8) s++
  if (/[A-Z]/.test(pw)) s++
  if (/\d/.test(pw)) s++
  if (/[^A-Za-z0-9]/.test(pw)) s++
  const levels = [
    { label: '', color: '#e8e8e8' },
    { label: 'Weak',   color: '#d32f2f' },
    { label: 'Fair',   color: '#f59e0b' },
    { label: 'Good',   color: '#3b82f6' },
    { label: 'Strong', color: '#16a34a' },
  ]
  return { score: s, ...levels[s] }
}

export default function Register() {
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '',
    department: '', password: '', confirmPassword: '',
    gdprConsent: false,
  })
  const [showPw,      setShowPw]      = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const register = useRegister()

  const strength       = getStrength(form.password)
  const passwordsMatch = form.password === form.confirmPassword || form.confirmPassword === ''
  const canSubmit      = form.gdprConsent && form.password === form.confirmPassword && form.password.length >= 8

  const errorMessage =
    register.error && 'response' in (register.error as object)
      ? ((register.error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
          'Registration failed — please try again.')
      : register.isError ? 'Registration failed — please try again.' : null

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    register.mutate({
      email: form.email, first_name: form.firstName, last_name: form.lastName,
      password: form.password, department: form.department || undefined, gdpr_consent: true,
    })
  }

  return (
    <AuthLayout>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ fontFamily: "'Anton', sans-serif", fontSize: '2.2rem', color: '#1a1a1a', letterSpacing: '0.03em' }}>
          CREATE ACCOUNT
        </div>
        <div style={{ display: 'block', width: '48px', height: '4px', background: '#FFCC00', margin: '0.9rem 0 0.7rem', borderRadius: '2px' }} />
        <div style={{ fontSize: '0.93rem', color: '#6b6b6b', fontWeight: 300 }}>
          Join the FORGE-Vision platform.
        </div>
      </div>

      {errorMessage && (
        <div style={{ background: '#fff5f5', border: '1.5px solid #f5c2c2', color: '#d32f2f', borderRadius: '8px', padding: '0.75rem 1rem', fontSize: '0.88rem', marginBottom: '1.2rem' }}>
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Name row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.2rem' }}>
          <div>
            <label style={L}>First Name</label>
            <input type="text" placeholder="John" value={form.firstName} required
              onChange={(e) => setForm((f) => ({ ...f, firstName: e.target.value }))}
              style={I} onFocus={focus} onBlur={blur} />
          </div>
          <div>
            <label style={L}>Last Name</label>
            <input type="text" placeholder="Smith" value={form.lastName} required
              onChange={(e) => setForm((f) => ({ ...f, lastName: e.target.value }))}
              style={I} onFocus={focus} onBlur={blur} />
          </div>
        </div>

        {/* Email */}
        <div style={{ marginBottom: '1.2rem' }}>
          <label style={L}>Email Address</label>
          <div style={{ position: 'relative' }}>
            <span style={ICON}>✉</span>
            <input type="email" placeholder="you@company.com" value={form.email} required
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              style={{ ...I, paddingLeft: '2.6rem' }} onFocus={focus} onBlur={blur} />
          </div>
        </div>

        {/* Department */}
        <div style={{ marginBottom: '1.2rem' }}>
          <label style={L}>Department <span style={{ fontWeight: 400, textTransform: 'none', opacity: 0.6 }}>(optional)</span></label>
          <input type="text" placeholder="e.g. Faculty of Science" value={form.department}
            onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
            style={I} onFocus={focus} onBlur={blur} />
        </div>

        {/* Password row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.5rem' }}>
          <div>
            <label style={L}>Password</label>
            <div style={{ position: 'relative' }}>
              <input type={showPw ? 'text' : 'password'} placeholder="••••••••" value={form.password} required
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                style={{ ...I, paddingRight: '2.4rem' }} onFocus={focus} onBlur={blur} />
              <button type="button" onClick={() => setShowPw((v) => !v)} style={TB}>
                {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <label style={L}>Confirm PW</label>
            <div style={{ position: 'relative' }}>
              <input type={showConfirm ? 'text' : 'password'} placeholder="••••••••" value={form.confirmPassword} required
                onChange={(e) => setForm((f) => ({ ...f, confirmPassword: e.target.value }))}
                style={{ ...I, paddingRight: '2.4rem', borderColor: !passwordsMatch && form.confirmPassword ? '#d32f2f' : '#e8e8e8' }}
                onFocus={focus} onBlur={blur} />
              <button type="button" onClick={() => setShowConfirm((v) => !v)} style={TB}>
                {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>

        {/* Password strength */}
        {form.password.length > 0 && (
          <div style={{ marginBottom: '0.8rem' }}>
            <div style={{ display: 'flex', gap: '4px', height: '5px', marginBottom: '4px' }}>
              {[1,2,3,4].map((i) => (
                <div key={i} style={{ flex: 1, borderRadius: '3px', background: strength.score >= i ? strength.color : '#e8e8e8', transition: 'background 0.2s' }} />
              ))}
            </div>
            {strength.label && <p style={{ fontSize: '0.75rem', color: '#6b6b6b' }}>Strength: <strong>{strength.label}</strong></p>}
          </div>
        )}

        {!passwordsMatch && form.confirmPassword.length > 0 && (
          <p style={{ fontSize: '0.75rem', color: '#d32f2f', marginBottom: '0.8rem' }}>Passwords do not match</p>
        )}

        {/* GDPR */}
        <div style={{ border: '1.5px solid #e8e8e8', borderRadius: '8px', padding: '0.85rem 1rem', marginBottom: '1.4rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
          <input
            type="checkbox"
            id="gdpr"
            checked={form.gdprConsent}
            onChange={(e) => setForm((f) => ({ ...f, gdprConsent: e.target.checked }))}
            style={{ width: '15px', height: '15px', marginTop: '2px', accentColor: '#FFCC00', flexShrink: 0 }}
          />
          <label htmlFor="gdpr" style={{ fontSize: '0.78rem', color: '#6b6b6b', cursor: 'pointer', lineHeight: 1.5 }}>
            I agree to the processing of my data in accordance with GDPR and the FORGE-Vision data protection policy.
          </label>
        </div>

        {/* Submit */}
        <button type="submit" disabled={!canSubmit || register.isPending} style={{ ...SUB, opacity: !canSubmit ? 0.6 : 1, cursor: !canSubmit ? 'not-allowed' : 'pointer' }}
          onMouseEnter={(e) => { if (canSubmit) e.currentTarget.style.background = '#E6B800' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#FFCC00' }}
        >
          {register.isPending ? 'Creating account…' : 'CREATE ACCOUNT →'}
        </button>
      </form>

      <div style={{ textAlign: 'center', margin: '1.4rem 0 0', fontSize: '0.9rem', color: '#6b6b6b' }}>
        Already registered?{' '}
        <Link to="/login" style={{ color: '#1a1a1a', fontWeight: 700, textDecoration: 'none', borderBottom: '2px solid #FFCC00', paddingBottom: '1px' }}>
          Sign in
        </Link>
      </div>

      <p style={{ textAlign: 'center', fontSize: '0.75rem', color: '#bbb', marginTop: '1.5rem', letterSpacing: '0.04em' }}>
        🔒 Secured · GDPR Compliant · AES-256 Encrypted
      </p>
    </AuthLayout>
  )
}

// ── Micro-styles ─────────────────────────────────────────────────────────────

const L: React.CSSProperties = { display: 'block', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#1a1a1a', marginBottom: '0.4rem' }
const I: React.CSSProperties = { width: '100%', padding: '0.78rem 1rem', border: '2px solid #e8e8e8', borderRadius: '8px', fontFamily: "'Source Sans 3', sans-serif", fontSize: '0.92rem', color: '#1a1a1a', background: '#FEFFFF', outline: 'none', transition: 'border-color 0.2s' }
const ICON: React.CSSProperties = { position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#6b6b6b', fontSize: '1rem', pointerEvents: 'none' }
const TB: React.CSSProperties = { position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#6b6b6b', display: 'flex', alignItems: 'center', padding: '4px' }
const SUB: React.CSSProperties = { width: '100%', padding: '1rem', background: '#FFCC00', color: '#1a1a1a', fontFamily: "'Anton', sans-serif", fontSize: '1.05rem', letterSpacing: '0.1em', border: 'none', borderRadius: '8px', transition: 'background 0.2s' }
const focus = (e: React.FocusEvent<HTMLInputElement>) => { e.currentTarget.style.borderColor = '#FFCC00' }
const blur  = (e: React.FocusEvent<HTMLInputElement>) => { e.currentTarget.style.borderColor = '#e8e8e8' }
