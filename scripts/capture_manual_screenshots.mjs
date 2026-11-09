#!/usr/bin/env node
import { existsSync } from 'node:fs'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..')
const require = createRequire(path.join(projectRoot, 'frontend', 'package.json'))
const { chromium } = require('playwright')

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4203'
const outDir = path.resolve(projectRoot, process.env.SCREENSHOT_OUT_DIR || 'docs/manuals/screenshots')
const email = process.env.SCREENSHOT_EMAIL || ''
const password = process.env.SCREENSHOT_PASSWORD || ''
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync(systemChromePath) ? systemChromePath : undefined)

const shots = [
  { id: 'SHOT-AUTH-001', file: 'auth-login.png', route: '/login' },
  { id: 'SHOT-DATA-001', file: 'data-readiness.png', route: '/data', tab: '就绪度' },
  { id: 'SHOT-DATA-004', file: 'data-experiment-feedback.png', route: '/data', tab: '实验反馈' },
  { id: 'SHOT-LIPASE-001', file: 'lipase-evidence-browser.png', route: '/data', tab: 'Lipase库' },
  { id: 'SHOT-OPS-001', file: 'ops-summary-alerts.png', route: '/data', tab: '监控' },
  { id: 'SHOT-ADMIN-001', file: 'admin-users.png', route: '/admin' },
]

async function maybeLogin(page) {
  if (!email || !password) return { attempted: false, status: 'credentials_not_provided' }
  await page.goto(new URL('/login', baseUrl).toString(), { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(750)
  const loginInput = page
    .locator('input[type="text"], input[type="email"], input[name="email"], input[name="username"]')
    .first()
  const passwordInput = page.locator('input[type="password"], input[name="password"]').first()
  if (!(await loginInput.count()) || !(await passwordInput.count())) {
    return { attempted: true, status: 'login_form_not_found' }
  }
  await loginInput.fill(email)
  await passwordInput.fill(password)
  const submitButton = page.locator('button[type="submit"], button').filter({ hasText: /登录|Login|Sign in/i }).first()
  if (!(await submitButton.count())) {
    return { attempted: true, status: 'login_button_not_found' }
  }
  await submitButton.click()
  await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(750)
  return { attempted: true, status: 'submitted', final_url: page.url() }
}

async function clickTabIfNeeded(page, tab) {
  if (!tab) return { clicked: false }
  const tabButton = page.getByRole('button', { name: tab }).first()
  if (!(await tabButton.count())) return { clicked: false, status: 'tab_not_found' }
  await tabButton.click()
  await page.waitForTimeout(750)
  return { clicked: true, status: 'ok' }
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 })
  const manifest = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    out_dir: path.relative(projectRoot, outDir),
    auth: await maybeLogin(page),
    screenshots: [],
  }

  for (const shot of shots) {
    const url = new URL(shot.route, baseUrl).toString()
    const target = path.join(outDir, shot.file)
    const startedAt = new Date().toISOString()
    let entry
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 })
      await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(750)
      const tab = await clickTabIfNeeded(page, shot.tab)
      await page.screenshot({ path: target, fullPage: true })
      const stat = await fs.stat(target)
      entry = {
        id: shot.id,
        file: path.relative(projectRoot, target),
        route: shot.route,
        tab: shot.tab || null,
        final_url: page.url(),
        status: 'captured',
        started_at: startedAt,
        size_bytes: stat.size,
        tab_result: tab,
      }
    } catch (error) {
      entry = {
        id: shot.id,
        file: path.relative(projectRoot, target),
        route: shot.route,
        tab: shot.tab || null,
        final_url: page.url(),
        status: 'failed',
        started_at: startedAt,
        error: error instanceof Error ? error.message : String(error),
      }
    }
    manifest.screenshots.push(entry)
  }

  await browser.close()
  const manifestPath = path.join(outDir, 'manifest.json')
  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

  console.log(`manual_screenshots\tstatus=ok\tcount=${manifest.screenshots.length}\tmanifest=${path.relative(projectRoot, manifestPath)}`)
  for (const entry of manifest.screenshots) {
    console.log(`${entry.id}\t${entry.status}\t${entry.file}\t${entry.final_url}`)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
