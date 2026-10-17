// Screenshot the running web dashboard with headless Chrome over the DevTools protocol.
// No dependencies (Node >= 22: global WebSocket and fetch). SYNTHETIC accounts only.
//
//   node tools/ui-qa/screenshots.mjs --out DIR --login EMAIL --password PW \
//        --api http://127.0.0.1:8000 --web http://127.0.0.1:5173 \
//        --sizes 1440x900,390x844 --routes /app/dashboard,/app/patients/ID/analytics [--scheme dark]
//
// Use the origin the API allows for CORS (SNEHA_CORS_ALLOWED_ORIGINS, default
// http://localhost:5173); 127.0.0.1 is a different origin and is refused.
//
// Each route is captured full-page at each size as DIR/<route>@<w>x<h>.png. A route
// may end in "#click=<text>" to click the first button or <summary> whose text starts with it.
// --prefix NAME prefixes file names (e.g. one run per role).
import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, v, i, a) => (v.startsWith('--') ? [...acc, [v.slice(2), a[i + 1]]] : acc), []),
)
const CHROME = args.chrome ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const out = args.out ?? 'screenshots'
const sizes = (args.sizes ?? '1440x900').split(',').map((s) => s.split('x').map(Number))
const routes = (args.routes ?? '/').split(',')
const port = 9333 + Math.floor(Math.random() * 500)
// A throwaway browser profile outside the output folder, removed at the end.
const profile = mkdtempSync(join(tmpdir(), 'sneha-ui-qa-chrome-'))
mkdirSync(out, { recursive: true })

let token = null
if (args.login) {
  const r = await fetch(`${args.api}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: args.login, password: args.password }),
  })
  if (!r.ok) throw new Error(`login failed: ${r.status}`)
  token = (await r.json()).access_token
}

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let target
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200)
  try {
    target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === 'page')
  } catch { /* not up yet */ }
}
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((r) => ws.addEventListener('open', r))
let id = 0
const pending = new Map()
ws.addEventListener('message', (e) => {
  const msg = JSON.parse(e.data)
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id) }
})
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const n = ++id
  pending.set(n, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)))
  ws.send(JSON.stringify({ id: n, method, params }))
})
const evaluate = async (expression) =>
  (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value

await send('Page.enable')
await send('Runtime.enable')
// --scheme light|dark (default light): independent of the machine's appearance setting.
await send('Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-color-scheme', value: args.scheme ?? 'light' }],
})
// Same origin first, so sessionStorage can hold the token like a real sign-in.
await send('Page.navigate', { url: args.web })
await sleep(800)
if (token) await evaluate(`sessionStorage.setItem('sneha.session.token', ${JSON.stringify(token)})`)
// --local KEY=JSON stores a localStorage value first (e.g. dashboard settings).
if (args.local) {
  const at = args.local.indexOf('=')
  await evaluate(`localStorage.setItem(${JSON.stringify(args.local.slice(0, at))}, ${JSON.stringify(args.local.slice(at + 1))})`)
}

const report = []
for (const [w, h] of sizes) {
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 })
  for (const route of routes) {
    const [path, action] = route.split('#')
    await send('Page.navigate', { url: args.web + path })
    await sleep(Number(args.wait ?? 1500))
    if (action?.startsWith('click=')) {
      const label = action.slice(6)
      await evaluate(`[...document.querySelectorAll('button, summary')].find(b => b.textContent.trim().startsWith(${JSON.stringify(label)}))?.click()`)
      await sleep(900)
    }
    const overflow = await evaluate('document.documentElement.scrollWidth - window.innerWidth')
    const height = await evaluate('Math.max(document.body.scrollHeight, window.innerHeight)')
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: Math.min(height, 6000), deviceScaleFactor: 1, mobile: w < 600 })
    await sleep(250)
    const shot = await send('Page.captureScreenshot', { format: 'png' })
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 })
    const name = `${args.prefix ? args.prefix + '_' : ''}${args.scheme === 'dark' ? 'dark_' : ''}${(path.replace(/^\/app\/?/, '').replace(/patients\/[0-9a-f-]{36}/, 'patient').replace(/\//g, '_') || 'root')}${action ? '_' + action.slice(6).replace(/\W+/g, '-') : ''}@${w}x${h}.png`
    writeFileSync(join(out, name), Buffer.from(shot.data, 'base64'))
    report.push({ file: name, horizontalOverflowPx: overflow, pageHeight: height })
  }
}
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report))
ws.close()
chrome.kill()
await sleep(500)
rmSync(profile, { recursive: true, force: true })
