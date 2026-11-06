import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

// No baseURL — all requests use relative paths (e.g. /api/v1/auth/login)
// so they are handled by Vite's dev-server proxy, avoiding mixed-content
// issues when the frontend is served over HTTPS.
const api = axios.create({
  withCredentials: true, // sends httpOnly refresh_token cookie automatically
  headers: { 'Content-Type': 'application/json' },
})

// Attach Bearer token from Zustand in-memory store on every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Prevent concurrent refresh attempts from stacking up
let isRefreshing = false

// On 401, attempt a silent token refresh then retry the original request once.
// Guards: skip if the failing request IS the refresh endpoint (avoids infinite
// loop), and skip if a refresh is already in flight.
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean }
    const isRefreshCall = (original.url ?? '').includes('/auth/refresh')

    if (error.response?.status === 401 && !original._retry && !isRefreshCall && !isRefreshing) {
      original._retry = true
      isRefreshing = true
      try {
        const { data } = await api.post<{ access_token: string }>('/api/v1/auth/refresh')
        useAuthStore.getState().setToken(data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  },
)

export default api
