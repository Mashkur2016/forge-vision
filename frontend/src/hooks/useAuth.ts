import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '@/lib/api'
import { useAuthStore, type AuthUser, type UserRole } from '@/store/authStore'

// ── Types ──────────────────────────────────────────────────────────────────

interface RegisterPayload {
  email: string
  first_name: string
  last_name: string
  password: string
  department?: string
  gdpr_consent: boolean
}

interface LoginPayload {
  email: string
  password: string
}

interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
  requires_mfa: false
}

interface PreAuthResponse {
  pre_auth_token: string
  requires_mfa: true
}

// ── Redirect helper ────────────────────────────────────────────────────────

async function redirectByRole(role: UserRole, navigate: ReturnType<typeof useNavigate>, token: string) {
  if (role === 'staff') {
    window.location.href = `https://localhost:8501/?token=${encodeURIComponent(token)}`
    return
  }

  // If the user clicked "Re-run Setup Wizard" before logging in, honour that
  // request regardless of what is saved in the database.
  if (localStorage.getItem('forge_force_wizard')) {
    localStorage.removeItem('forge_force_wizard')
    localStorage.removeItem('forge_onboarding_done')
    navigate('/onboarding')
    return
  }

  // For trainer / manager / admin: check whether LLM settings exist in the
  // database. If yes → onboarding was completed, go to dashboard. If no →
  // show the wizard. This is reliable regardless of browser/localStorage state.
  try {
    const { data } = await api.get('/api/v1/settings/active-provider')
    if (data && data.provider) {
      // Settings already configured — mark flag and go to dashboard
      localStorage.setItem('forge_onboarding_done', 'true')
      window.location.href = `https://localhost:8501/?token=${encodeURIComponent(token)}`
      return
    }
  } catch {
    // If the request fails (network error, 404, etc.) fall through to wizard
  }

  // No settings found — run the wizard
  localStorage.removeItem('forge_onboarding_done')
  navigate('/onboarding')
}

// ── Hooks ──────────────────────────────────────────────────────────────────

export function useLogin() {
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (data: LoginPayload) =>
      api.post<AuthResponse | PreAuthResponse>('/api/v1/auth/login', data).then((r) => r.data),
    onSuccess: async (data) => {
      if (data.requires_mfa) {
        sessionStorage.setItem('pre_auth_token', (data as PreAuthResponse).pre_auth_token)
        navigate('/mfa')
      } else {
        const res = data as AuthResponse
        setAuth(res.user, res.access_token)
        await redirectByRole(res.user.role, navigate, res.access_token)
      }
    },
  })
}

export function useRegister() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (data: RegisterPayload) =>
      api.post('/api/v1/auth/register', data).then((r) => r.data),
    onSuccess: () => navigate('/login?registered=1'),
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (data: { email: string }) =>
      api.post('/api/v1/auth/forgot-password', data).then((r) => r.data),
  })
}

export function useResetPassword() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (data: { token: string; new_password: string }) =>
      api.post('/api/v1/auth/reset-password', data).then((r) => r.data),
    onSuccess: () => navigate('/login?message=password_reset'),
  })
}

export function useMFAVerify() {
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (data: { totp_code: string; pre_auth_token: string }) =>
      api.post<AuthResponse>('/api/v1/auth/verify-mfa', data).then((r) => r.data),
    onSuccess: async (data) => {
      sessionStorage.removeItem('pre_auth_token')
      setAuth(data.user, data.access_token)
      await redirectByRole(data.user.role, navigate, data.access_token)
    },
  })
}
