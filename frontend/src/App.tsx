import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import ForgotPassword from '@/pages/ForgotPassword'
import ResetPassword from '@/pages/ResetPassword'
import MFAVerification from '@/pages/MFAVerification'
import LiveTraining from '@/pages/LiveTraining'
import OnboardingWizard from '@/pages/OnboardingWizard'

function SetupReset() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  useEffect(() => {
    localStorage.removeItem('forge_onboarding_done')
    if (isAuthenticated) {
      navigate('/onboarding', { replace: true })
    } else {
      // Not logged in yet — store a flag so redirectByRole sends the user
      // to the wizard immediately after their next login.
      localStorage.setItem('forge_force_wizard', 'true')
      navigate('/login', { replace: true })
    }
  }, [])
  return null
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/mfa" element={<MFAVerification />} />
          <Route
            path="/training/live"
            element={
              <PrivateRoute>
                <LiveTraining />
              </PrivateRoute>
            }
          />
          <Route
            path="/onboarding"
            element={
              <PrivateRoute>
                <OnboardingWizard />
              </PrivateRoute>
            }
          />
          {/* /setup clears the onboarding flag so the wizard runs again */}
          <Route path="/setup" element={<SetupReset />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
