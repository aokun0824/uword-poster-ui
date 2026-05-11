import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    server: {
      port: 5200,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:5201',
          changeOrigin: true
        }
      }
    },
    define: {
      __API_BASE__: JSON.stringify(env.VITE_API_BASE || '')
    }
  }
})
