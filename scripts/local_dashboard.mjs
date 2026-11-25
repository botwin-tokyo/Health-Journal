// Static dashboard for this Pi only. Health records are fetched from the Pi API.
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dist=path.join(root,'frontend/dist');
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.woff':'font/woff','.woff2':'font/woff2','.wasm':'application/wasm','.bcmap':'application/octet-stream','.ttf':'font/ttf'};
const tlsDir = process.env.HEALTH03_PI_APPLIANCE === '1' ? process.env.CREDENTIALS_DIRECTORY : path.join(root, '.local/frontend-tls');
https.createServer({key:fs.readFileSync(path.join(tlsDir,'localhost.key')),cert:fs.readFileSync(path.join(tlsDir,'localhost.pem'))},(req,res)=>{
 if(req.headers.host!=='localhost:5173'||!['GET','HEAD'].includes(req.method)){res.writeHead(403);res.end();return;}
 let pathname;try{pathname=decodeURIComponent(new URL(req.url,'https://localhost:5173').pathname);}catch{res.writeHead(400);res.end();return;}
 let file=path.resolve(dist,'.'+pathname);
 if(!file.startsWith(dist+path.sep)){file=path.join(dist,'index.html');}
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){if(path.extname(pathname)){res.writeHead(404);res.end();return;}file=path.join(dist,'index.html');}
 res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':file.includes('/assets/')?'public, max-age=31536000, immutable':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; font-src 'self'; img-src 'self' blob: data:; connect-src 'self' https://localhost:8443; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"});
 if(req.method==='HEAD'){res.end();return;}fs.createReadStream(file).pipe(res);
}).listen(5173,'127.0.0.1',()=>console.log('Local dashboard: https://localhost:5173'));
