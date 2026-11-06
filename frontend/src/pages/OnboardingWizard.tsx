import { useEffect, useState } from 'react'
import api from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

type Provider = 'groq' | 'gemini' | 'openai' | 'ollama'

const PROVIDERS: { id: Provider; label: string; free: boolean; hint: string; icon: string }[] = [
  { id: 'groq',   label: 'Groq',              free: true,  hint: 'llama-3.1-8b-instant', icon: '⚡' },
  { id: 'gemini', label: 'Google Gemini',      free: true,  hint: 'gemini-1.5-flash',     icon: '✦' },
  { id: 'openai', label: 'OpenAI GPT-4o mini', free: false, hint: 'gpt-4o-mini',           icon: '◈' },
  { id: 'ollama', label: 'Ollama Local',        free: false, hint: 'llama3.1:8b',           icon: '⬡' },
]

const PROVIDER_MODELS: Record<Provider, string> = {
  groq:   'llama-3.1-8b-instant',
  gemini: 'gemini-1.5-flash',
  openai: 'gpt-4o-mini',
  ollama: 'llama3.1:8b',
}

// ── Design tokens ──────────────────────────────────────────────────────────────
const GOLD    = '#FFCC00'
const GOLD_D  = '#E6B800'
const DARK    = '#0f0f0f'
const SIDEBAR = '#111827'   // deep navy-black
const WHITE   = '#ffffff'
const OFF_W   = '#F7F8FA'
const BORDER  = '#E5E7EB'
const MUTED   = '#6B7280'
const SUCCESS = '#16A34A'
const DANGER  = '#DC2626'

// ── Fonts ──────────────────────────────────────────────────────────────────────
const anton: React.CSSProperties = { fontFamily: "'Anton', sans-serif" }
const ss3:   React.CSSProperties = { fontFamily: "'Source Sans 3', sans-serif" }

// ── Shared micro-styles ────────────────────────────────────────────────────────
const labelSt: React.CSSProperties = {
  display: 'block', fontSize: '0.7rem', fontWeight: 700,
  letterSpacing: '0.1em', textTransform: 'uppercase', color: '#374151',
  marginBottom: '0.5rem',
}

const inputSt: React.CSSProperties = {
  width: '100%', padding: '0.75rem 1rem',
  border: `1.5px solid ${BORDER}`, borderRadius: '8px',
  fontFamily: "'Source Sans 3', sans-serif", fontSize: '0.95rem',
  color: DARK, background: WHITE, outline: 'none',
  transition: 'border-color 0.2s, box-shadow 0.2s', boxSizing: 'border-box',
}

const primaryBtn: React.CSSProperties = {
  padding: '0.78rem 1.4rem', background: GOLD, color: DARK,
  fontFamily: "'Anton', sans-serif", fontSize: '0.92rem',
  letterSpacing: '0.07em', border: 'none', borderRadius: '8px',
  cursor: 'pointer', transition: 'background 0.18s, transform 0.1s',
  whiteSpace: 'nowrap',
}

const ghostBtn: React.CSSProperties = {
  padding: '0.78rem 1.2rem', background: 'transparent', color: MUTED,
  fontFamily: "'Anton', sans-serif", fontSize: '0.88rem',
  letterSpacing: '0.06em', border: `1.5px solid ${BORDER}`, borderRadius: '8px',
  cursor: 'pointer', transition: 'all 0.18s', whiteSpace: 'nowrap',
}

const disabledBtn: React.CSSProperties = {
  ...primaryBtn, background: '#E9EAEC', color: '#aaa', cursor: 'not-allowed',
}

// ── Step definitions ───────────────────────────────────────────────────────────
const STEPS = [
  { num: 1 as const, label: 'Configure AI',  desc: 'Connect an LLM provider', icon: '🤖' },
  { num: 2 as const, label: 'Select SOP',    desc: 'Pick a training procedure', icon: '📋' },
  { num: 3 as const, label: 'Launch',        desc: 'Review & start training',   icon: '🚀' },
]

// ── Sidebar ────────────────────────────────────────────────────────────────────
function Sidebar({ current }: { current: 1 | 2 | 3 }) {
  return (
    <div style={{
      width: '260px', flexShrink: 0,
      background: SIDEBAR,
      display: 'flex', flexDirection: 'column',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Gold top accent line */}
      <div style={{ height: '3px', background: `linear-gradient(90deg, ${GOLD}, transparent)` }} />

      {/* Logo */}
      <div style={{ padding: '1.8rem 1.6rem 1.4rem' }}>
        <img
          src="/logo2.jpg"
          alt="FORGE-Vision"
          style={{ width: '160px', display: 'block', objectFit: 'contain', marginBottom: '0.5rem' }}
        />
        <div style={{
          fontSize: '0.65rem', letterSpacing: '0.18em', textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.35)', fontWeight: 700,
        }}>
          Setup Wizard
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '0 1.6rem' }} />

      {/* Steps */}
      <div style={{ padding: '1.4rem 0', flex: 1 }}>
        {STEPS.map(({ num, label, desc, icon }, i) => {
          const active = num === current
          const done   = num < current

          return (
            <div key={num}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '0.85rem 1.6rem',
                background: active ? 'rgba(255,204,0,0.10)' : 'transparent',
                borderLeft: active ? `3px solid ${GOLD}` : '3px solid transparent',
                transition: 'all 0.2s',
              }}>
                {/* Step bubble */}
                <div style={{
                  width: '34px', height: '34px', borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: done
                    ? GOLD
                    : active
                    ? 'rgba(255,204,0,0.15)'
                    : 'rgba(255,255,255,0.06)',
                  border: `2px solid ${done ? GOLD : active ? `rgba(255,204,0,0.6)` : 'rgba(255,255,255,0.12)'}`,
                  transition: 'all 0.25s',
                }}>
                  {done
                    ? <span style={{ fontSize: '0.85rem', color: DARK, fontWeight: 900 }}>✓</span>
                    : active
                    ? <span style={{ fontSize: '1rem' }}>{icon}</span>
                    : <span style={{ ...anton, fontSize: '0.78rem', color: 'rgba(255,255,255,0.3)' }}>{num}</span>
                  }
                </div>

                <div>
                  <div style={{
                    fontSize: '0.88rem', fontWeight: 700, lineHeight: 1.2,
                    color: done ? 'rgba(255,255,255,0.5)' : active ? WHITE : 'rgba(255,255,255,0.3)',
                  }}>
                    {label}
                  </div>
                  <div style={{
                    fontSize: '0.72rem', marginTop: '2px',
                    color: active ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.2)',
                  }}>
                    {desc}
                  </div>
                </div>
              </div>

              {/* Connector */}
              {i < STEPS.length - 1 && (
                <div style={{
                  width: '2px', height: '16px',
                  background: num < current ? GOLD : 'rgba(255,255,255,0.1)',
                  margin: '0 0 0 calc(1.6rem + 16px)',
                  transition: 'background 0.3s',
                }} />
              )}
            </div>
          )
        })}
      </div>

      {/* Bottom badges */}
      <div style={{
        padding: '1.2rem 1.6rem',
        borderTop: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {['🔒 GDPR Compliant', '🔐 AES-256 Encrypted', '🎓 DBA Research System'].map((t) => (
            <span key={t} style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.28)', letterSpacing: '0.03em' }}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Step 1: LLM ────────────────────────────────────────────────────────────────
function Step1LLM({ onNext }: { onNext: () => void }) {
  const [provider,    setProvider]    = useState<Provider>('groq')
  const [apiKey,      setApiKey]      = useState('')
  const [ollamaUrl,   setOllamaUrl]   = useState('http://host.docker.internal:11434')
  const [testStatus,  setTestStatus]  = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [testMessage, setTestMessage] = useState('')
  const [saving,      setSaving]      = useState(false)

  async function handleTest() {
    setTestStatus('testing'); setTestMessage('')
    try {
      const { data } = await api.post('/api/v1/settings/test', {
        provider, model_name: PROVIDER_MODELS[provider],
        api_key: provider !== 'ollama' ? apiKey : null,
        ollama_base_url: provider === 'ollama' ? ollamaUrl : null,
      })
      setTestStatus(data.success ? 'ok' : 'fail')
      setTestMessage(data.message)
    } catch {
      setTestStatus('fail')
      setTestMessage('Connection failed — check your key and try again.')
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.post('/api/v1/settings', {
        provider, model_name: PROVIDER_MODELS[provider],
        api_key: provider !== 'ollama' ? apiKey : null,
        ollama_base_url: provider === 'ollama' ? ollamaUrl : null,
      })
      if (testStatus === 'ok') {
        await api.post('/api/v1/settings/test', {
          provider, model_name: PROVIDER_MODELS[provider],
          api_key: provider !== 'ollama' ? apiKey : null,
          ollama_base_url: provider === 'ollama' ? ollamaUrl : null,
        }).catch(() => {})
      }
      onNext()
    } catch { setSaving(false) }
  }

  const canSave = !saving && (provider === 'ollama' || apiKey.length > 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
      {/* Provider grid */}
      <div>
        <label style={labelSt}>AI Language Model Provider</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.55rem' }}>
          {PROVIDERS.map((p) => {
            const sel = provider === p.id
            return (
              <label key={p.id} style={{
                display: 'flex', flexDirection: 'column', gap: '4px',
                padding: '0.9rem 1rem',
                border: `1.5px solid ${sel ? GOLD : BORDER}`,
                borderRadius: '10px',
                background: sel ? 'rgba(255,204,0,0.06)' : OFF_W,
                cursor: 'pointer', transition: 'all 0.15s',
                position: 'relative',
              }}>
                <input type="radio" name="provider" value={p.id} checked={sel}
                  onChange={() => { setProvider(p.id); setTestStatus('idle') }}
                  style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '1.1rem' }}>{p.icon}</span>
                  {sel
                    ? <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: GOLD }} />
                    : p.free && (
                      <span style={{
                        fontSize: '0.58rem', fontWeight: 800, color: SUCCESS,
                        background: '#DCFCE7', padding: '2px 6px', borderRadius: '10px',
                        letterSpacing: '0.05em',
                      }}>FREE</span>
                    )
                  }
                </div>
                <span style={{ fontSize: '0.87rem', fontWeight: 700, color: sel ? DARK : '#555' }}>{p.label}</span>
                <span style={{ fontSize: '0.68rem', color: '#aaa', fontFamily: 'monospace' }}>{p.hint}</span>
              </label>
            )
          })}
        </div>
      </div>

      {/* Credential field */}
      {provider !== 'ollama' ? (
        <div>
          <label style={labelSt}>API Key</label>
          <input type="password" placeholder="Paste your API key here…"
            value={apiKey} onChange={(e) => { setApiKey(e.target.value); setTestStatus('idle') }}
            style={inputSt}
            onFocus={(e) => { e.currentTarget.style.borderColor = GOLD; e.currentTarget.style.boxShadow = `0 0 0 3px rgba(255,204,0,0.12)` }}
            onBlur={(e)  => { e.currentTarget.style.borderColor = BORDER; e.currentTarget.style.boxShadow = 'none' }}
          />
        </div>
      ) : (
        <div>
          <label style={labelSt}>Ollama Base URL</label>
          <input value={ollamaUrl} onChange={(e) => { setOllamaUrl(e.target.value); setTestStatus('idle') }}
            style={inputSt}
            onFocus={(e) => { e.currentTarget.style.borderColor = GOLD; e.currentTarget.style.boxShadow = `0 0 0 3px rgba(255,204,0,0.12)` }}
            onBlur={(e)  => { e.currentTarget.style.borderColor = BORDER; e.currentTarget.style.boxShadow = 'none' }}
          />
        </div>
      )}

      {/* Test result */}
      {testStatus !== 'idle' && (
        <div style={{
          padding: '0.65rem 1rem', borderRadius: '8px', fontSize: '0.85rem',
          background: testStatus === 'ok' ? '#F0FDF4' : testStatus === 'fail' ? '#FEF2F2' : OFF_W,
          color:      testStatus === 'ok' ? SUCCESS   : testStatus === 'fail' ? DANGER   : MUTED,
          border:     `1.5px solid ${testStatus === 'ok' ? '#BBF7D0' : testStatus === 'fail' ? '#FECACA' : BORDER}`,
          display: 'flex', alignItems: 'center', gap: '0.5rem',
        }}>
          {testStatus === 'testing' && <><span>⏳</span> Testing connection…</>}
          {testStatus === 'ok'      && <><span>✅</span> {testMessage}</>}
          {testStatus === 'fail'    && <><span>❌</span> {testMessage}</>}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.55rem', paddingTop: '0.2rem' }}>
        <button onClick={onNext} style={{ ...ghostBtn, flex: 1 }}>Skip</button>
        <button type="button" onClick={handleTest} disabled={testStatus === 'testing'}
          style={{ ...ghostBtn, flex: 1, borderColor: GOLD, color: DARK }}>
          {testStatus === 'testing' ? 'Testing…' : 'Test'}
        </button>
        <button type="button" onClick={handleSave} disabled={!canSave}
          style={{ ...(canSave ? primaryBtn : disabledBtn), flex: 2 }}
          onMouseEnter={(e) => { if (canSave) e.currentTarget.style.background = GOLD_D }}
          onMouseLeave={(e) => { if (canSave) e.currentTarget.style.background = GOLD }}
        >
          {saving ? 'Saving…' : 'Save & Continue →'}
        </button>
      </div>
    </div>
  )
}

// ── Step 2: SOP ────────────────────────────────────────────────────────────────
interface SopSummary {
  id: string; name: string; version?: string; category?: string
  step_count?: number; estimated_duration_seconds?: number
}

function SopHeroCard({ sop }: { sop: SopSummary }) {
  const dur = sop.estimated_duration_seconds
    ? `${Math.round(sop.estimated_duration_seconds / 60)} min`
    : null

  return (
    <div style={{
      background: `linear-gradient(135deg, ${SIDEBAR} 0%, #1e293b 100%)`,
      borderRadius: '12px', padding: '1.4rem 1.6rem',
      border: `1.5px solid rgba(255,204,0,0.3)`,
      position: 'relative', overflow: 'hidden',
      marginTop: '0.8rem',
    }}>
      {/* Gold accent top-left */}
      <div style={{
        position: 'absolute', top: 0, left: 0, width: '4px', height: '100%',
        background: `linear-gradient(180deg, ${GOLD}, transparent)`,
      }} />

      <div style={{ paddingLeft: '0.6rem' }}>
        <div style={{
          fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: GOLD, marginBottom: '0.5rem',
        }}>
          Selected SOP
        </div>
        <div style={{ ...anton, fontSize: '1.35rem', color: WHITE, lineHeight: 1.2, marginBottom: '0.9rem' }}>
          {sop.name}
        </div>

        {/* Stat pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {sop.step_count != null && (
            <span style={{
              fontSize: '0.75rem', fontWeight: 700, color: DARK,
              background: GOLD, padding: '3px 10px', borderRadius: '20px',
            }}>
              {sop.step_count} steps
            </span>
          )}
          {dur && (
            <span style={{
              fontSize: '0.75rem', fontWeight: 600,
              color: 'rgba(255,255,255,0.85)', background: 'rgba(255,255,255,0.1)',
              padding: '3px 10px', borderRadius: '20px',
              border: '1px solid rgba(255,255,255,0.15)',
            }}>
              ⏱ {dur}
            </span>
          )}
          {sop.category && (
            <span style={{
              fontSize: '0.75rem', fontWeight: 600,
              color: 'rgba(255,255,255,0.85)', background: 'rgba(255,255,255,0.1)',
              padding: '3px 10px', borderRadius: '20px',
              border: '1px solid rgba(255,255,255,0.15)',
            }}>
              {sop.category}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function Step2SOP({ onNext, onBack }: { onNext: (id: string, name: string) => void; onBack: () => void }) {
  const [sops,     setSops]     = useState<SopSummary[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const selectedSop = sops.find((s) => s.id === selected) ?? null

  useEffect(() => {
    api.get<SopSummary[]>('/api/v1/sops/')
      .then((r) => { setSops(r.data); setLoading(false) })
      .catch(() => { setError('Could not load SOPs — is the backend running?'); setLoading(false) })
  }, [])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '3rem 0', color: MUTED }}>
      <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>⏳</div>
      <p style={{ margin: 0, fontSize: '0.9rem' }}>Loading SOPs…</p>
    </div>
  )

  if (error || sops.length === 0) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
      <div style={{
        border: `2px dashed ${BORDER}`, borderRadius: '10px', padding: '2.2rem',
        textAlign: 'center', background: OFF_W,
      }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.6rem' }}>📭</div>
        <p style={{ margin: '0 0 0.3rem', fontSize: '0.92rem', color: MUTED }}>
          {error ?? 'No SOPs found. Use SOP Builder in the dashboard to create one.'}
        </p>
        <p style={{ margin: 0, fontSize: '0.8rem', color: '#bbb' }}>You can skip and choose a SOP when starting a session.</p>
      </div>
      <div style={{ display: 'flex', gap: '0.55rem' }}>
        <button onClick={onBack} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
        <button onClick={() => onNext('', '')} style={{ ...primaryBtn, flex: 2 }}
          onMouseEnter={(e) => { e.currentTarget.style.background = GOLD_D }}
          onMouseLeave={(e) => { e.currentTarget.style.background = GOLD }}>
          Continue without SOP →
        </button>
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <label style={labelSt}>Available Procedures</label>

      {/* SOP list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '240px', overflowY: 'auto', paddingRight: '2px' }}>
        {sops.map((sop) => {
          const sel = selected === sop.id
          const dur = sop.estimated_duration_seconds
            ? `${Math.round(sop.estimated_duration_seconds / 60)} min`
            : null

          return (
            <label key={sop.id} style={{
              display: 'flex', alignItems: 'center', gap: '0.9rem',
              padding: '0.9rem 1.1rem',
              border: `1.5px solid ${sel ? GOLD : BORDER}`,
              borderRadius: '10px',
              background: sel ? 'rgba(255,204,0,0.06)' : WHITE,
              cursor: 'pointer', transition: 'all 0.15s',
              boxShadow: sel ? `0 0 0 3px rgba(255,204,0,0.15)` : 'none',
            }}>
              {/* Radio dot */}
              <div style={{
                width: '18px', height: '18px', borderRadius: '50%', flexShrink: 0,
                border: `2px solid ${sel ? GOLD : '#D1D5DB'}`,
                background: sel ? GOLD : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s',
              }}>
                {sel && <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: DARK }} />}
              </div>
              <input type="radio" name="sop" value={sop.id} checked={sel}
                onChange={() => setSelected(sop.id)} style={{ display: 'none' }} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  margin: 0, fontSize: '0.92rem', fontWeight: 700, color: DARK,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {sop.name}
                </p>
                <p style={{ margin: '2px 0 0', fontSize: '0.74rem', color: '#9CA3AF', display: 'flex', gap: '0.5rem' }}>
                  {sop.step_count != null && <span>{sop.step_count} steps</span>}
                  {dur && <span>· {dur}</span>}
                  {sop.category && <span>· {sop.category}</span>}
                </p>
              </div>

              {sel && (
                <span style={{
                  fontSize: '0.65rem', fontWeight: 800, color: DARK,
                  background: GOLD, padding: '2px 8px', borderRadius: '10px', flexShrink: 0,
                }}>SELECTED</span>
              )}
            </label>
          )
        })}
      </div>

      {/* Hero card for selected SOP */}
      {selectedSop && <SopHeroCard sop={selectedSop} />}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.55rem', paddingTop: '0.4rem' }}>
        <button onClick={onBack} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
        <button onClick={() => onNext('', '')} style={{ ...ghostBtn, flex: 1 }}>Skip</button>
        <button
          onClick={() => {
            if (selected) localStorage.setItem('forge_default_sop', selected)
            onNext(selected ?? '', sops.find((s) => s.id === selected)?.name ?? '')
          }}
          disabled={!selected}
          style={{ ...(selected ? primaryBtn : disabledBtn), flex: 2 }}
          onMouseEnter={(e) => { if (selected) e.currentTarget.style.background = GOLD_D }}
          onMouseLeave={(e) => { if (selected) e.currentTarget.style.background = GOLD }}
        >
          {selected ? 'Use this SOP →' : 'Select a SOP'}
        </button>
      </div>
    </div>
  )
}

// ── Step 3: Ready ──────────────────────────────────────────────────────────────
function Step3Ready({ onBack, selectedSopId, selectedSopName }: {
  onBack: () => void; selectedSopId: string; selectedSopName: string
}) {
  const [llmStatus, setLlmStatus] = useState<{ provider: string; model: string } | null>(null)
  const [launching, setLaunching] = useState(false)
  const { accessToken } = useAuthStore()

  useEffect(() => {
    api.get('/api/v1/settings')
      .then((r) => r.data ? setLlmStatus({ provider: r.data.provider, model: r.data.model_name }) : null)
      .catch(() => null)
  }, [])

  function handleGoToDashboard() {
    setLaunching(true)
    if (selectedSopId) localStorage.setItem('forge_default_sop', selectedSopId)
    localStorage.setItem('forge_onboarding_done', 'true')

    const url = new URL('https://localhost:8501/')
    url.searchParams.set('token', accessToken ?? '')
    if (selectedSopId)   url.searchParams.set('sop_id', selectedSopId)
    if (selectedSopName) url.searchParams.set('sop_name', selectedSopName)
    window.location.href = url.toString()
  }

  const checklist = [
    {
      ok: !!llmStatus,
      label: 'AI Provider',
      value: llmStatus ? `${llmStatus.provider} — ${llmStatus.model}` : 'Not configured (optional)',
      icon: '🤖',
    },
    {
      ok: !!selectedSopName,
      label: 'Training SOP',
      value: selectedSopName || 'None selected (choose in Live Training)',
      icon: '📋',
    },
    {
      ok: true,
      label: 'Dashboard',
      value: 'Streamlit · localhost:8501',
      icon: '📊',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.3rem' }}>

      {/* SOP hero — shown prominently if selected */}
      {selectedSopName && (
        <div style={{
          background: `linear-gradient(135deg, ${SIDEBAR} 0%, #1e3a5f 100%)`,
          borderRadius: '12px', padding: '1.4rem 1.6rem',
          border: `1.5px solid rgba(255,204,0,0.35)`,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: 0, left: 0, width: '4px', height: '100%',
            background: GOLD,
          }} />
          <div style={{ paddingLeft: '0.7rem' }}>
            <div style={{
              fontSize: '0.58rem', fontWeight: 800, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: GOLD, marginBottom: '0.4rem',
            }}>
              Ready to Train On
            </div>
            <div style={{ ...anton, fontSize: '1.4rem', color: WHITE, lineHeight: 1.2 }}>
              {selectedSopName}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.5)', marginTop: '0.4rem' }}>
              This SOP will be pre-loaded when you open Live Training.
            </div>
          </div>
        </div>
      )}

      {/* Setup checklist */}
      <div style={{
        border: `1.5px solid ${BORDER}`, borderRadius: '10px', overflow: 'hidden',
      }}>
        {checklist.map(({ ok, label, value, icon }, i) => (
          <div key={label} style={{
            display: 'flex', alignItems: 'center', gap: '0.9rem',
            padding: '0.85rem 1.1rem', fontSize: '0.88rem',
            background: i % 2 === 0 ? WHITE : OFF_W,
            borderBottom: i < checklist.length - 1 ? `1px solid ${BORDER}` : 'none',
          }}>
            <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>{icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.72rem', color: MUTED, fontWeight: 600, letterSpacing: '0.04em' }}>{label}</div>
              <div style={{
                fontWeight: 700, color: DARK,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{value}</div>
            </div>
            <div style={{
              width: '20px', height: '20px', borderRadius: '50%', flexShrink: 0,
              background: ok ? '#DCFCE7' : '#FEF3C7',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.75rem',
            }}>
              {ok ? '✓' : '—'}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.55rem', paddingTop: '0.2rem' }}>
        <button onClick={onBack} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
        <button onClick={handleGoToDashboard} disabled={launching}
          style={{ ...(launching ? disabledBtn : primaryBtn), flex: 3 }}
          onMouseEnter={(e) => { if (!launching) e.currentTarget.style.background = GOLD_D }}
          onMouseLeave={(e) => { if (!launching) e.currentTarget.style.background = GOLD }}>
          {launching ? 'Launching…' : 'Launch Training Dashboard →'}
        </button>
      </div>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function OnboardingWizard() {
  const [step,            setStep]            = useState<1 | 2 | 3>(1)
  const [selectedSopId,   setSelectedSopId]   = useState('')
  const [selectedSopName, setSelectedSopName] = useState('')

  const stepMeta = {
    1: {
      tag: 'Step 01 / 03',
      title: 'Configure AI Model',
      sub: 'FORGE-Vision uses an LLM to generate real-time corrective feedback. Connect a provider to get started — you can change this any time.',
    },
    2: {
      tag: 'Step 02 / 03',
      title: 'Select Your SOP',
      sub: 'Choose the Standard Operating Procedure workers will train on first. The selected SOP will open automatically when you launch Live Training.',
    },
    3: {
      tag: 'Step 03 / 03',
      title: "You're All Set",
      sub: 'Review your configuration and launch the training dashboard. Everything you selected will be pre-loaded and ready.',
    },
  }[step]

  return (
    <div style={{ ...ss3, minHeight: '100vh', background: OFF_W, display: 'flex', flexDirection: 'column' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Anton&family=Source+Sans+3:wght@400;600;700&display=swap');
        * { box-sizing: border-box; }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 4px; }
      `}</style>

      {/* ── Top bar ── */}
      <div style={{
        height: '54px', background: WHITE,
        borderBottom: `1px solid ${BORDER}`,
        display: 'flex', alignItems: 'center',
        padding: '0 2rem', gap: '0', flexShrink: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}>
        <div style={{ width: '4px', height: '26px', background: GOLD, borderRadius: '2px', marginRight: '0.9rem' }} />
        <span style={{ ...anton, fontSize: '1.05rem', color: DARK, letterSpacing: '0.08em' }}>FORGE-VISION</span>
        <span style={{ fontSize: '0.75rem', color: MUTED, marginLeft: '0.7rem', letterSpacing: '0.04em' }}>/ Setup Wizard</span>

        {/* Progress dots */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          {[1, 2, 3].map((n) => (
            <div key={n} style={{
              width: n === step ? '24px' : '7px', height: '7px',
              borderRadius: '4px',
              background: n < step ? GOLD : n === step ? DARK : BORDER,
              transition: 'all 0.35s cubic-bezier(0.22,1,0.36,1)',
            }} />
          ))}
          <span style={{ fontSize: '0.75rem', color: MUTED, marginLeft: '0.5rem' }}>{step} / 3</span>
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        <Sidebar current={step} />

        {/* Main scroll area */}
        <div style={{
          flex: 1, display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
          padding: '2.8rem 2rem 3rem', overflowY: 'auto',
        }}>
          <div style={{
            width: '100%', maxWidth: '540px',
            animation: 'fadeUp 0.35s cubic-bezier(0.22,1,0.36,1) both',
          }}>
            {/* Step label + heading */}
            <div style={{ marginBottom: '2rem' }}>
              <div style={{
                display: 'inline-flex', alignItems: 'center',
                fontSize: '0.67rem', fontWeight: 800, letterSpacing: '0.16em',
                textTransform: 'uppercase', color: DARK,
                background: GOLD, padding: '3px 12px', borderRadius: '20px',
                marginBottom: '0.9rem',
              }}>
                {stepMeta.tag}
              </div>
              <h1 style={{ ...anton, fontSize: '2.1rem', color: DARK, margin: '0 0 0.6rem', letterSpacing: '0.01em', lineHeight: 1.1 }}>
                {stepMeta.title}
              </h1>
              <div style={{ width: '36px', height: '3px', background: GOLD, borderRadius: '2px', marginBottom: '0.7rem' }} />
              <p style={{ margin: 0, fontSize: '0.88rem', color: MUTED, lineHeight: 1.65, maxWidth: '460px' }}>
                {stepMeta.sub}
              </p>
            </div>

            {/* Card */}
            <div style={{
              background: WHITE, borderRadius: '14px',
              border: `1.5px solid ${BORDER}`,
              boxShadow: '0 4px 24px rgba(0,0,0,0.07)',
              padding: '2rem',
            }}>
              {step === 1 && <Step1LLM onNext={() => setStep(2)} />}
              {step === 2 && (
                <Step2SOP
                  onNext={(id, name) => { setSelectedSopId(id); setSelectedSopName(name); setStep(3) }}
                  onBack={() => setStep(1)}
                />
              )}
              {step === 3 && (
                <Step3Ready
                  onBack={() => setStep(2)}
                  selectedSopId={selectedSopId}
                  selectedSopName={selectedSopName}
                />
              )}
            </div>

            <p style={{
              textAlign: 'center', fontSize: '0.7rem', color: '#C4C7CC',
              marginTop: '1.4rem', letterSpacing: '0.04em',
            }}>
              Secured · GDPR Compliant · AES-256 Encrypted
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
