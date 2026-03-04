import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                // Disable compression so SSE events stream through immediately
                configure: (proxy) => {
                    proxy.on('proxyReq', (proxyReq) => {
                        // Tell the backend we accept uncompressed SSE
                        proxyReq.setHeader('Accept-Encoding', 'identity')
                    })
                    proxy.on('proxyRes', (proxyRes) => {
                        // Remove any content-encoding that would cause buffering
                        delete proxyRes.headers['content-encoding']
                        // Disable nginx/uvicorn buffering
                        proxyRes.headers['x-accel-buffering'] = 'no'
                        proxyRes.headers['cache-control'] = 'no-cache'
                    })
                },
            },
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
            },
        },
    },
})
