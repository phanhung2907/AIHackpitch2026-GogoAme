import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Nghe mọi interface để máy khác trong cùng wifi mở được UI; dùng cho demo LAN,
    // không phải cấu hình production. Thêm domain tunnel vào allowedHosts nếu mở ra Internet.
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app'],
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
