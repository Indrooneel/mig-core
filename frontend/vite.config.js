import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/validate': 'http://localhost:8000',
      '/approve': 'http://localhost:8000',
      '/reject': 'http://localhost:8000',
      '/policies': 'http://localhost:8000',
      '/zones': 'http://localhost:8000',
      '/audit': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
    }
  }
})
