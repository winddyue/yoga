import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 构建配置：API 地址通过环境变量 VITE_API_URL 注入，默认同域 /api
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    },
  },
})
