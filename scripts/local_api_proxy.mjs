// Loopback TLS proxy. Never log request bodies, URLs or credentials.
import https from 'node:https';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const port = Number(process.env.HEALTH03_PROXY_PORT || 8443);
const upstreamPort = Number(process.env.HEALTH03_UPSTREAM_PORT || 8000);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const credentials = process.env.CREDENTIALS_DIRECTORY;
const appliance = process.env.HEALTH03_PI_APPLIANCE === '1';
const tlsDir = appliance ? credentials : path.join(root, '.local/frontend-tls');
const desktopSecret = appliance
  ? fs.readFileSync(path.join(credentials, 'desktop-proxy-secret'), 'utf8').trim()
  : '';
if (appliance && !desktopSecret) throw Error('Missing desktop proxy credential');

https.createServer({
  key: fs.readFileSync(path.join(tlsDir, 'localhost.key')),
  cert: fs.readFileSync(path.join(tlsDir, 'localhost.pem')),
}, (req, res) => {
  if (req.headers.host !== `localhost:${port}`) {
    res.writeHead(403).end();
    return;
  }
  const headers = {...req.headers};
  delete headers['x-health03-origin'];
  delete headers['x-health03-desktop'];
  if (appliance) headers['x-health03-desktop'] = desktopSecret;
  const proxy = http.request({
    hostname: '127.0.0.1', port: upstreamPort, path: req.url, method: req.method, headers,
  }, upstream => {
    res.writeHead(upstream.statusCode || 502, upstream.headers);
    upstream.pipe(res);
  });
  proxy.on('error', () => {
    res.writeHead(502, {'Content-Type':'application/json', 'Cache-Control':'no-store'});
    res.end('{"code":"pi_unavailable"}');
  });
  req.on('aborted', () => proxy.destroy());
  req.pipe(proxy);
}).listen(port, '127.0.0.1');
