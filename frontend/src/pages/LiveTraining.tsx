import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle, CheckCircle2, Clock, Factory, SkipForward, Video,
  Volume2, VolumeX, Wifi, WifiOff,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { useWebSocket } from '@/hooks/useWebSocket'
import api from '@/lib/api'

// ── Types ──────────────────────────────────────────────────────────────────
interface SopStep {
  id: number
  name: string
  description: string
  safety_critical?: boolean
  time_limit_seconds?: number
}
interface SopSummary { id: string; name: string; step_count?: number; category?: string }
interface FeedbackEvent {
  deviation_class: string
  severity: 'low' | 'medium' | 'high'
  feedback_text: string
  step_name: string
  timestamp: string
}
interface StepOutcome { id: number; name: string; status: 'completed' | 'skipped'; reason?: string }
type SessionState = 'setup' | 'connecting' | 'active' | 'stopped'

const SEVERITY_COLORS: Record<string, string> = {
  low:    'bg-yellow-50 border-yellow-300 text-yellow-900',
  medium: 'bg-orange-50 border-orange-300 text-orange-900',
  high:   'bg-red-50   border-red-300    text-red-900',
}

export default function LiveTraining() {
  const videoRef  = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  const [sessionState, setSessionState] = useState<SessionState>('setup')
  const [sessionId,    setSessionId]    = useState<string | null>(null)
  const [manualMode,   setManualMode]   = useState(false)
  const [wsUrl,        setWsUrl]        = useState<string | null>(null)

  const [sops,        setSops]        = useState<SopSummary[]>([])
  const [selectedSop, setSelectedSop] = useState<string>('')
  const [steps,       setSteps]       = useState<SopStep[]>([])

  const [currentIndex, setCurrentIndex] = useState(0)
  const [outcomes,     setOutcomes]     = useState<StepOutcome[]>([])
  const [safetyAck,    setSafetyAck]    = useState(false)
  const [feedback,     setFeedback]     = useState<FeedbackEvent[]>([])

  const [elapsed,     setElapsed]     = useState(0)
  const [stepElapsed, setStepElapsed] = useState(0)
  const [frameCount,  setFrameCount]  = useState(0)
  const [ttsEnabled,  setTtsEnabled]  = useState(true)

  const currentStep = steps[currentIndex]

  // ── Load SOP list on mount ──────────────────────────────────────────────
  useEffect(() => {
    api.get<SopSummary[]>('/api/v1/sops/')
      .then((r) => {
        const list = Array.isArray(r.data) ? r.data : []
        setSops(list)
        if (list.length > 0) setSelectedSop(list[0].id)
      })
      .catch(() => setSops([]))
  }, [])

  // Load step preview when the selected SOP changes (so the worker sees the procedure first)
  useEffect(() => {
    if (!selectedSop) { setSteps([]); return }
    api.get(`/api/v1/sops/${selectedSop}`)
      .then((r) => setSteps(Array.isArray(r.data?.steps) ? r.data.steps : []))
      .catch(() => setSteps([]))
  }, [selectedSop])

  // ── TTS (browser Web Speech API) ─────────────────────────────────────────
  const speakFeedback = useCallback((text: string, severity: string) => {
    if (!window.speechSynthesis || severity === 'low') return
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    utt.rate = severity === 'high' ? 1.2 : 1.0
    window.speechSynthesis.speak(utt)
  }, [])

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const { status: wsStatus, lastMessage } = useWebSocket(wsUrl)
  const wsConnected = wsStatus === 'open'

  useEffect(() => {
    if (!lastMessage) return
    try {
      const msg = JSON.parse(lastMessage.data as string)
      setFrameCount((n) => n + 1)
      if (msg.event === 'deviation' || msg.type === 'deviation') {
        const d = msg.data ?? msg
        const ev: FeedbackEvent = {
          deviation_class: d.deviation_class ?? 'unknown',
          severity:        d.severity ?? 'low',
          feedback_text:   d.feedback_text ?? d.feedback ?? 'Review the current step.',
          step_name:       d.step_name ?? d.expected_step_name ?? '',
          timestamp:       new Date().toLocaleTimeString(),
        }
        setFeedback((prev) => [ev, ...prev].slice(0, 12))
        if (ttsEnabled) speakFeedback(ev.feedback_text, ev.severity)
      }
    } catch { /* non-JSON frame is fine */ }
  }, [lastMessage, ttsEnabled, speakFeedback])

  // ── Camera ──────────────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch { /* camera unavailable — manual mode still works */ }
  }
  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }

  // ── Session lifecycle ─────────────────────────────────────────────────────
  const handleStart = async () => {
    if (!selectedSop) return
    setSessionState('connecting')
    setFeedback([]); setOutcomes([]); setCurrentIndex(0)
    setElapsed(0); setStepElapsed(0); setFrameCount(0); setSafetyAck(false)
    await startCamera()

    let mode = true // assume manual until the backend confirms a live pipeline
    try {
      const { data } = await api.post('/api/v1/session/start', {
        sop_id: selectedSop, camera_source: 0, tts_enabled: true,
      })
      const sid = data.session_id as string
      setSessionId(sid)
      mode = false
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      setWsUrl(`${proto}//${window.location.host}/api/v1/session/ws/${sid}`)
    } catch {
      // 503 / unreachable pipeline → manual mode with a local session id
      setSessionId(`local-${Date.now()}`)
      mode = true
    }
    setManualMode(mode)
    setSessionState('active')
    timerRef.current = setInterval(() => {
      setElapsed((s) => s + 1)
      setStepElapsed((s) => s + 1)
    }, 1000)
  }

  const finish = useCallback(async () => {
    window.speechSynthesis?.cancel()
    setWsUrl(null)
    stopCamera()
    if (timerRef.current) clearInterval(timerRef.current)
    setSessionState('stopped')
    if (sessionId && !sessionId.startsWith('local-')) {
      try { await api.post(`/api/v1/session/${sessionId}/stop`) } catch { /* best-effort */ }
    }
  }, [sessionId])

  // ── Step controls ─────────────────────────────────────────────────────────
  const advance = (status: 'completed' | 'skipped', reason?: string) => {
    if (!currentStep) return
    setOutcomes((prev) => [...prev, { id: currentStep.id, name: currentStep.name, status, reason }])
    setSafetyAck(false)
    setStepElapsed(0)
    const next = currentIndex + 1
    setCurrentIndex(next)
    if (next >= steps.length) void finish()
  }

  const handleComplete = () => {
    if (currentStep?.safety_critical && !safetyAck) return
    advance('completed')
  }
  const handleSkip = () => {
    const reason = window.prompt('Reason for skipping this step? (optional)') ?? undefined
    advance('skipped', reason || undefined)
  }

  useEffect(() => () => {
    stopCamera()
    if (timerRef.current) clearInterval(timerRef.current)
    window.speechSynthesis?.cancel()
  }, [])

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const completedCount = useMemo(() => outcomes.filter((o) => o.status === 'completed').length, [outcomes])
  const score = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0
  const overTime = currentStep?.time_limit_seconds ? stepElapsed > currentStep.time_limit_seconds : false

  // ── Render: SETUP ─────────────────────────────────────────────────────────
  if (sessionState === 'setup') {
    return (
      <Shell ttsEnabled={ttsEnabled} setTtsEnabled={setTtsEnabled} wsConnected={false} state="setup" elapsed={0} frames={0}>
        <div className="col-span-12 max-w-2xl mx-auto w-full">
          <Card>
            <CardHeader className="py-3 px-5 border-b"><span className="font-semibold">Session Setup</span></CardHeader>
            <CardContent className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Standard Operating Procedure</label>
                <select
                  value={selectedSop}
                  onChange={(e) => setSelectedSop(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 bg-background text-sm"
                >
                  {sops.length === 0 && <option value="">No SOPs available</option>}
                  {sops.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}{s.step_count ? ` (${s.step_count} steps)` : ''}</option>
                  ))}
                </select>
              </div>
              {steps.length > 0 && (
                <div className="border rounded-md p-3 bg-muted/30">
                  <div className="text-xs font-semibold text-muted-foreground mb-2">PROCEDURE PREVIEW</div>
                  <ol className="space-y-1 text-sm list-decimal list-inside">
                    {steps.map((st) => (
                      <li key={st.id}>
                        {st.name}
                        {st.safety_critical && <span className="ml-2 text-xs text-orange-600 font-medium">safety-critical</span>}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              <button
                onClick={handleStart}
                disabled={!selectedSop}
                className="w-full bg-primary text-primary-foreground py-2.5 rounded-md font-semibold hover:bg-primary/90 transition disabled:opacity-50"
              >
                ▶ Start Session
              </button>
              <p className="text-xs text-muted-foreground text-center">
                The browser camera is used for live monitoring where available; otherwise the session runs in
                step-by-step manual mode.
              </p>
            </CardContent>
          </Card>
        </div>
      </Shell>
    )
  }

  // ── Render: SUMMARY ─────────────────────────────────────────────────────────
  if (sessionState === 'stopped') {
    return (
      <Shell ttsEnabled={ttsEnabled} setTtsEnabled={setTtsEnabled} wsConnected={false} state="stopped" elapsed={elapsed} frames={frameCount}>
        <div className="col-span-12 max-w-3xl mx-auto w-full space-y-4">
          <Card>
            <CardHeader className="py-3 px-5 border-b"><span className="font-semibold">Session Summary</span></CardHeader>
            <CardContent className="p-5">
              <div className="grid grid-cols-4 gap-3 text-center mb-5">
                <Metric value={fmt(elapsed)} label="Duration" />
                <Metric value={`${completedCount}/${steps.length}`} label="Steps completed" />
                <Metric value={String(feedback.length)} label="Deviations" tone="destructive" />
                <Metric value={`${score}%`} label="Completion score" tone="primary" />
              </div>
              <div className="text-xs font-semibold text-muted-foreground mb-2">STEP OUTCOMES</div>
              <ul className="divide-y text-sm border rounded-md">
                {outcomes.map((o, i) => (
                  <li key={i} className="flex items-center justify-between px-3 py-2">
                    <span>{o.name}</span>
                    {o.status === 'completed'
                      ? <span className="text-green-600 flex items-center gap-1"><CheckCircle2 className="h-4 w-4" />Completed</span>
                      : <span className="text-orange-600 flex items-center gap-1"><SkipForward className="h-4 w-4" />Skipped{o.reason ? ` — ${o.reason}` : ''}</span>}
                  </li>
                ))}
              </ul>
              <button
                onClick={() => { setSessionState('setup'); setSessionId(null); setManualMode(false) }}
                className="mt-5 w-full border py-2 rounded-md font-medium hover:bg-muted transition"
              >
                Start New Session
              </button>
            </CardContent>
          </Card>
        </div>
      </Shell>
    )
  }

  // ── Render: ACTIVE / CONNECTING ─────────────────────────────────────────────
  return (
    <Shell ttsEnabled={ttsEnabled} setTtsEnabled={setTtsEnabled} wsConnected={wsConnected} state={sessionState} elapsed={elapsed} frames={frameCount} manualMode={manualMode} onStop={finish}>
      {/* Camera (left) */}
      <div className="col-span-12 md:col-span-5 flex flex-col gap-3">
        <Card className="flex-1 overflow-hidden">
          <CardHeader className="py-2 px-4 border-b"><span className="font-semibold text-sm flex items-center gap-2"><Video className="h-4 w-4" /> Camera Feed</span></CardHeader>
          <CardContent className="p-0 relative bg-black" style={{ minHeight: '320px' }}>
            <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" style={{ minHeight: '320px' }} />
            {manualMode && (
              <div className="absolute top-2 left-2 bg-yellow-400/90 text-black text-xs font-semibold px-2 py-1 rounded">
                Manual mode — camera pipeline unavailable
              </div>
            )}
            {sessionState === 'connecting' && (
              <div className="absolute inset-0 flex items-center justify-center"><span className="text-white text-sm animate-pulse">Connecting…</span></div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Current step + controls (centre) */}
      <div className="col-span-12 md:col-span-4 flex flex-col gap-3">
        <Card className="flex-1">
          <CardHeader className="py-2 px-4 border-b flex-row items-center justify-between">
            <span className="font-semibold text-sm">Current Step {currentStep ? `(${currentIndex + 1}/${steps.length})` : ''}</span>
            <span className={`text-xs flex items-center gap-1 ${overTime ? 'text-red-600 font-semibold' : 'text-muted-foreground'}`}>
              <Clock className="h-3.5 w-3.5" />{fmt(stepElapsed)}{currentStep?.time_limit_seconds ? ` / ${fmt(currentStep.time_limit_seconds)}` : ''}
            </span>
          </CardHeader>
          <CardContent className="p-4">
            {currentStep ? (
              <>
                <div className="flex items-start gap-2 mb-2">
                  {currentStep.safety_critical && <AlertTriangle className="h-5 w-5 text-orange-500 shrink-0 mt-0.5" />}
                  <div>
                    <div className="font-semibold">{currentStep.name}</div>
                    <p className="text-sm text-muted-foreground mt-1">{currentStep.description}</p>
                  </div>
                </div>
                {overTime && <div className="text-xs text-red-600 mb-2">Step time limit exceeded.</div>}
                {currentStep.safety_critical && (
                  <label className="flex items-center gap-2 text-sm mb-3 p-2 bg-orange-50 border border-orange-200 rounded">
                    <input type="checkbox" checked={safetyAck} onChange={(e) => setSafetyAck(e.target.checked)} />
                    I confirm this safety-critical step was performed correctly.
                  </label>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={handleComplete}
                    disabled={currentStep.safety_critical && !safetyAck}
                    className="flex-1 bg-primary text-primary-foreground py-2 rounded-md text-sm font-semibold hover:bg-primary/90 transition disabled:opacity-50"
                  >
                    ✓ Mark Complete
                  </button>
                  <button onClick={handleSkip} className="px-3 py-2 border rounded-md text-sm hover:bg-muted transition flex items-center gap-1">
                    <SkipForward className="h-4 w-4" /> Skip
                  </button>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-6">All steps addressed — finishing…</p>
            )}
          </CardContent>
        </Card>

        {/* Progress list */}
        <Card>
          <CardContent className="p-3">
            <ol className="space-y-1.5">
              {steps.map((st, idx) => {
                const outcome = outcomes.find((o) => o.id === st.id)
                const active  = idx === currentIndex
                return (
                  <li key={st.id} className={['flex items-center gap-2 text-sm rounded px-2 py-1',
                    outcome?.status === 'completed' ? 'text-green-700'
                      : outcome?.status === 'skipped' ? 'text-orange-600'
                      : active ? 'font-semibold text-primary' : 'text-muted-foreground'].join(' ')}>
                    {outcome?.status === 'completed' ? <CheckCircle2 className="h-4 w-4 text-green-600" />
                      : outcome?.status === 'skipped' ? <SkipForward className="h-4 w-4" />
                      : <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px]">{idx + 1}</span>}
                    {st.name}
                  </li>
                )
              })}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* AI feedback (right) */}
      <div className="col-span-12 md:col-span-3">
        <Card className="h-full">
          <CardHeader className="py-2 px-4 border-b"><span className="font-semibold text-sm">AI Feedback</span></CardHeader>
          <CardContent className="p-3 overflow-y-auto" style={{ maxHeight: '520px' }}>
            {feedback.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center mt-8">
                {manualMode ? 'Manual mode — AI deviation feedback requires the live camera pipeline.' : 'No deviations detected — keep going!'}
              </p>
            ) : (
              <ul className="space-y-2">
                {feedback.map((ev, i) => (
                  <li key={i} className={['rounded-md border p-3 text-sm', SEVERITY_COLORS[ev.severity] ?? SEVERITY_COLORS.low].join(' ')}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold capitalize">{ev.deviation_class.replace(/_/g, ' ')}</span>
                      <span className="text-xs opacity-70">{ev.timestamp}</span>
                    </div>
                    {ev.step_name && <div className="text-xs opacity-70 mb-1">Step: {ev.step_name}</div>}
                    <div>{ev.feedback_text}</div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </Shell>
  )
}

// ── Layout shell (header + grid) ─────────────────────────────────────────────
function Shell(props: {
  children: ReactNode
  ttsEnabled: boolean
  setTtsEnabled: (v: boolean) => void
  wsConnected: boolean
  state: SessionState
  elapsed: number
  frames: number
  manualMode?: boolean
  onStop?: () => void
}) {
  const { children, ttsEnabled, setTtsEnabled, wsConnected, state, elapsed, frames, manualMode, onStop } = props
  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="border-b px-6 py-3 flex items-center justify-between bg-card shadow-sm">
        <div className="flex items-center gap-2"><Factory className="h-6 w-6 text-primary" /><span className="font-bold text-lg">FORGE-Vision — Live Training</span></div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <button onClick={() => setTtsEnabled(!ttsEnabled)} className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-muted transition">
            {ttsEnabled ? <><Volume2 className="h-4 w-4 text-primary" />Voice on</> : <><VolumeX className="h-4 w-4" />Voice off</>}
          </button>
          {state === 'active' && (
            <>
              <span className="flex items-center gap-1">
                {wsConnected ? <><Wifi className="h-4 w-4 text-green-600" />Live</> : <><WifiOff className="h-4 w-4" />{manualMode ? 'Manual' : 'Connecting'}</>}
              </span>
              <span className="flex items-center gap-1"><Clock className="h-4 w-4" />{fmt(elapsed)}</span>
              {!manualMode && <span className="text-xs">Frames: {frames}</span>}
              {onStop && <button onClick={onStop} className="text-xs bg-destructive text-destructive-foreground px-3 py-1.5 rounded-md font-medium hover:bg-destructive/90 transition">Stop Session</button>}
            </>
          )}
        </div>
      </header>
      <div className="flex-1 grid grid-cols-12 gap-4 p-4 overflow-auto">{children}</div>
    </div>
  )
}

function Metric({ value, label, tone }: { value: string; label: string; tone?: 'primary' | 'destructive' }) {
  const color = tone === 'destructive' ? 'text-destructive' : tone === 'primary' ? 'text-primary' : ''
  return <div><div className={`text-2xl font-bold ${color}`}>{value}</div><div className="text-xs text-muted-foreground">{label}</div></div>
}
