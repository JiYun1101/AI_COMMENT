import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Presentation preview is isolated from the main Render services.
// Only the separately provisioned frontend preview uses /api; its reverse proxy
// calls the existing backend without changing backend CORS settings or deploying it.
const previewHost = 'ai-comment-presentation-20261028.onrender.com'

export default defineConfig({
  plugins: [react()],
  preview: {
    allowedHosts: ['ai-comment-web.onrender.com', previewHost],
    proxy: {
      '/api': {
        target: 'https://ai-comment-api-lite.onrender.com',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api(?=\/|$)/, ''),
      },
    },
  },
})
