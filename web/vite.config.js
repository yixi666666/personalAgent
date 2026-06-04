import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8001,
    proxy: {
      '/v1': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
})
