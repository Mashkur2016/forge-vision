import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Factory } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useResetPassword } from '@/hooks/useAuth'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const resetPassword = useResetPassword()

  const passwordsMatch = password === confirm || confirm === ''
  const canSubmit = password.length >= 8 && password === confirm && !!token

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit || !token) return
    resetPassword.mutate({ token, new_password: password })
  }

  const errorMessage =
    resetPassword.error && 'response' in (resetPassword.error as object)
      ? ((resetPassword.error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
          'Reset failed — the link may have expired.')
      : resetPassword.isError
        ? 'Reset failed — the link may have expired.'
        : null

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="text-center space-y-4">
          <p className="text-error font-medium">Invalid reset link</p>
          <p className="text-sm text-muted-foreground">
            This link is missing the reset token. Please request a new one.
          </p>
          <Link to="/forgot-password" className="text-primary hover:underline text-sm">
            Request new link →
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <div className="flex justify-end p-4">
        <ThemeToggle />
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md space-y-6">
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-2 text-primary">
              <Factory className="h-8 w-8" />
              <span className="text-2xl font-bold tracking-tight">FORGE-Vision</span>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Set new password</CardTitle>
              <CardDescription>
                Choose a strong password — at least 8 characters, one uppercase letter, one digit.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">New password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPw ? 'text' : 'password'}
                      placeholder="••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="pr-10"
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                      onClick={() => setShowPw((v) => !v)}
                      aria-label="Toggle password visibility"
                    >
                      {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm">Confirm new password</Label>
                  <Input
                    id="confirm"
                    type="password"
                    placeholder="••••••••••"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                  />
                  {!passwordsMatch && confirm.length > 0 && (
                    <p className="text-xs text-error">Passwords do not match</p>
                  )}
                </div>

                {errorMessage && (
                  <p className="text-sm text-error">{errorMessage}</p>
                )}

                <Button type="submit" className="w-full" disabled={!canSubmit || resetPassword.isPending}>
                  {resetPassword.isPending ? 'Resetting…' : 'Reset Password →'}
                </Button>

                <Link to="/login" className="block text-center text-sm text-muted-foreground hover:text-foreground">
                  ← Back to Sign In
                </Link>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
