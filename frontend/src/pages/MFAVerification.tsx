import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Factory, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useMFAVerify } from '@/hooks/useAuth'

const DIGIT_COUNT = 6
const CODE_TTL = 30 // seconds per TOTP window

export default function MFAVerification() {
  const navigate = useNavigate()
  const [digits, setDigits] = useState<string[]>(Array(DIGIT_COUNT).fill(''))
  const [secondsLeft, setSecondsLeft] = useState(CODE_TTL)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  const mfaVerify = useMFAVerify()

  const preAuthToken = sessionStorage.getItem('pre_auth_token')

  // Redirect away if there's no pre_auth_token (direct navigation)
  useEffect(() => {
    if (!preAuthToken) navigate('/login', { replace: true })
  }, [preAuthToken, navigate])

  // Countdown timer
  useEffect(() => {
    const id = setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : CODE_TTL))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  // Auto-submit when all 6 digits are filled
  useEffect(() => {
    const code = digits.join('')
    if (code.length === DIGIT_COUNT && !digits.includes('') && preAuthToken) {
      mfaVerify.mutate({ totp_code: code, pre_auth_token: preAuthToken })
    }
  }, [digits]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      if (digits[index]) {
        // Clear current
        setDigits((d) => {
          const next = [...d]
          next[index] = ''
          return next
        })
      } else if (index > 0) {
        // Move focus back and clear
        inputRefs.current[index - 1]?.focus()
        setDigits((d) => {
          const next = [...d]
          next[index - 1] = ''
          return next
        })
      }
    }
  }

  function handleChange(index: number, value: string) {
    const char = value.replace(/\D/g, '').slice(-1)
    if (!char) return
    setDigits((d) => {
      const next = [...d]
      next[index] = char
      return next
    })
    if (index < DIGIT_COUNT - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  function handleResend() {
    setDigits(Array(DIGIT_COUNT).fill(''))
    setSecondsLeft(CODE_TTL)
    inputRefs.current[0]?.focus()
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')

  const errorMessage = mfaVerify.isError ? 'Invalid MFA code — please try again.' : null

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <div className="flex justify-end p-4">
        <ThemeToggle />
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-6">
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-2 text-primary">
              <Factory className="h-8 w-8" />
              <span className="text-2xl font-bold tracking-tight">FORGE-Vision</span>
            </div>
          </div>

          <Card>
            <CardHeader className="text-center">
              <div className="flex justify-center mb-2">
                <ShieldCheck className="h-10 w-10 text-primary" />
              </div>
              <CardTitle>Two-Factor Authentication</CardTitle>
              <CardDescription>
                🔐 Open your authenticator app and enter the 6-digit code.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Digit boxes */}
              <div className="flex justify-center gap-2">
                {Array.from({ length: DIGIT_COUNT }).map((_, i) => (
                  <input
                    key={i}
                    ref={(el) => { inputRefs.current[i] = el }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digits[i]}
                    onChange={(e) => handleChange(i, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    className="w-11 h-12 text-center text-xl font-semibold rounded-input border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
                    aria-label={`Digit ${i + 1}`}
                  />
                ))}
              </div>

              {errorMessage && (
                <p className="text-sm text-error text-center">{errorMessage}</p>
              )}

              {mfaVerify.isPending && (
                <p className="text-sm text-muted-foreground text-center">Verifying…</p>
              )}

              {/* Timer */}
              <div className="text-center text-sm text-muted-foreground">
                Code expires in{' '}
                <span className="font-mono font-medium text-foreground">
                  {mm}:{ss}
                </span>
              </div>

              <div className="text-center text-sm text-muted-foreground">
                Didn&apos;t receive it?{' '}
                <button
                  type="button"
                  onClick={handleResend}
                  className="text-primary hover:underline font-medium"
                >
                  Resend code
                </button>
              </div>

              <Button
                variant="ghost"
                className="w-full text-sm"
                onClick={() => navigate('/login')}
              >
                ← Sign in as different user
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
