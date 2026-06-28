import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O painel é servido pela API do Monitor em /painel, então os assets usam base '/painel/'.
// Em desenvolvimento (npm run dev), o proxy encaminha /cortes para a API local (porta 8000).
export default defineConfig({
  plugins: [react()],
  base: '/painel/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/cortes': 'http://localhost:8000',
    },
  },
})
