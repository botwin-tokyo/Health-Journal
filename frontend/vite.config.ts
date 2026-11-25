import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
const cert = '../.local/frontend-tls/localhost.pem', key = '../.local/frontend-tls/localhost.key';
const https = fs.existsSync(cert) ? { cert: fs.readFileSync(cert), key: fs.readFileSync(key) } : undefined;
export default defineConfig(({ mode }) => ({envDir:"..", plugins: [react(), {name:"development-only-msw",configureServer(server){server.middlewares.use((req,res,next)=>{if(mode==="mock"&&req.url==="/mockServiceWorker.js"){res.setHeader("Content-Type","text/javascript");res.end(fs.readFileSync("node_modules/msw/lib/mockServiceWorker.js"));}else next();});}}], define: {__JOURNAL_TIMEZONE__: JSON.stringify(loadEnv(mode,"..","JOURNAL_TIMEZONE").JOURNAL_TIMEZONE || "UTC"), __SAMPLE_MODE__: JSON.stringify(mode === 'mock')}, server: {host:'127.0.0.1', port:5173, strictPort:true, https}, preview:{host:'127.0.0.1',port:5173,strictPort:true,https}, build: {sourcemap:false,chunkSizeWarningLimit:600}, test:{environment:'jsdom',include:['src/**/*.test.{ts,tsx}']}}));
