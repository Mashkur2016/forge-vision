import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

// SSL certs live in <project-root>/ssl/ — one level above frontend/
const sslDir  = path.resolve(__dirname, '../ssl')
const certFile = path.join(sslDir, 'localhost.pem')
const keyFile  = path.join(sslDir, 'localhost-key.pem')
const certsExist = fs.existsSync(certFile) && fs.existsSync(keyFile)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    // Enable HTTPS automatically when mkcert certs are present in ssl/
    https: certsExist
      ? { key: fs.readFileSync(keyFile), cert: fs.readFileSync(certFile) }
      : undefined,
    proxy: {
      '/api': {
        // FastAPI stays on HTTP internally — Vite proxies server-side so the
        // browser only ever sees the HTTPS Vite origin (no mixed-content issue).
        // API_PROXY_TARGET has no VITE_ prefix so it is never baked into the
        // browser bundle — only the Node.js vite process reads it.
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
