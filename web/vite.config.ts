import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Served from https://<user>.github.io/rehearsal-grounds/ on GitHub Pages.
export default defineConfig({
  base: '/rehearsal-grounds/',
  plugins: [react()],
})
