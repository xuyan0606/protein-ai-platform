import fs from 'node:fs'
import { chromium } from 'playwright'

const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage()
const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4201'

try {
  await page.goto(`${baseUrl}/smoke-tests.html`, { waitUntil: 'networkidle' })

  await page.waitForSelector('[data-testid="mutation-score-card"]')
  const mutationText = await page.locator('[data-testid="mutation-score-card"]').textContent()
  if (
    !mutationText?.includes('候选突变位点') ||
    !mutationText.includes('首轮决策') ||
    !mutationText.includes('Go') ||
    !mutationText.includes('Watch') ||
    !mutationText.includes('No-Go') ||
    !mutationText.includes('位点/编号') ||
    !mutationText.includes('机制逻辑') ||
    !mutationText.includes('PDB') ||
    !mutationText.includes('UniProt') ||
    !mutationText.includes('A:42') ||
    !mutationText.includes('G42P') ||
    !mutationText.includes('K118E') ||
    !mutationText.includes('首轮实验候选位点') ||
    !mutationText.includes('预期方向') ||
    !mutationText.includes('风险提示') ||
    !mutationText.includes('P1') ||
    !mutationText.includes('P2') ||
    !mutationText.includes('探索性') ||
    !mutationText.includes('未映射') ||
    !mutationText.includes('D86') ||
    !mutationText.includes('D275') ||
    !mutationText.includes('禁止突变')
  ) {
    throw new Error(`Mutation score table did not render bench-facing fields: ${mutationText}`)
  }
  const mutationSiteIndex = mutationText.indexOf('候选突变位点')
  const strategyIndex = mutationText.indexOf('改造策略')
  if (mutationSiteIndex < 0 || strategyIndex < 0 || strategyIndex > mutationSiteIndex) {
    throw new Error('Strategy explanation must be shown before mutation site table')
  }

  await page.waitForSelector('[data-testid="blocked-mutation-score-card"]')
  const blockedMutationText = await page.locator('[data-testid="blocked-mutation-score-card"]').textContent()
  if (
    !blockedMutationText?.includes('突变候选输出门控') ||
    !blockedMutationText.includes('本轮不输出具体突变候选') ||
    !blockedMutationText.includes('身份或编号门控未通过，未生成候选') ||
    !blockedMutationText.includes('No-Go门控') ||
    blockedMutationText.includes('候选突变位点') ||
    blockedMutationText.includes('P2-探索')
  ) {
    throw new Error(`Blocked identity mutation card did not render gate-only state: ${blockedMutationText}`)
  }

  const mutationTables = page.locator('[data-testid="mutation-score-card"] table')
  const mutationTableCount = await mutationTables.count()
  let mutationTableHeaders = []
  for (let index = 0; index < mutationTableCount; index += 1) {
    const headers = await mutationTables.nth(index).locator('thead th').allTextContents()
    if (headers.join('|').includes('位点/编号')) {
      mutationTableHeaders = headers
      break
    }
  }
  const normalizedHeaders = mutationTableHeaders.join('|')
  if (normalizedHeaders !== '优先级|位点/编号|推荐突变|机制逻辑|主要风险') {
    throw new Error(`Mutation candidate table should stay compact, got headers: ${normalizedHeaders}`)
  }

  await page.locator('[data-testid="toolcall-card"] button').click()

  await page.waitForSelector('text=注释工具包')
  await page.waitForSelector('text=InterPro 条目')
  await page.waitForSelector('text=保护位点')
  await page.waitForSelector('text=Provide sequence or uniprot_id')
  await page.waitForSelector('text=388 aa 蛋白稳定性提升实验执行清单')
  await page.waitForSelector('text=Go / No-Go 决策标准')
  await page.waitForSelector('text=最终输出目标')

  const metricText = await page.locator('[data-testid="bundle-card"]').textContent()
  if (!metricText?.includes('DEMO388A') || !metricText.includes('252')) {
    throw new Error(`Unexpected bundle metric content: ${metricText}`)
  }

  const markdownText = await page.locator('[data-testid="markdown-card"]').textContent()
  if (
    !markdownText?.includes('M1') ||
    !markdownText.includes('Tm 提升 >= 2°C') ||
    !markdownText.includes('第一轮结束后')
  ) {
    throw new Error(`Markdown checklist content was not fully rendered: ${markdownText}`)
  }

  const nestedTableCount = await page.locator('[data-testid="markdown-card"] table table').count()
  if (nestedTableCount !== 0) {
    throw new Error(`Markdown table rendered with invalid nested tables: ${nestedTableCount}`)
  }

  const streamingTableCount = await page.locator('[data-testid="streaming-table-card"] table').count()
  if (streamingTableCount < 1) {
    throw new Error('Streaming markdown table did not render as an HTML table')
  }

  const streamingTableText = await page.locator('[data-testid="streaming-table-card"]').textContent()
  if (
    !streamingTableText?.includes('Unknown enzyme family') ||
    !streamingTableText.includes('input_required') ||
    streamingTableText.includes('|---|---||')
  ) {
    throw new Error(`Streaming markdown table content was not normalized: ${streamingTableText}`)
  }

  const ecTableText = await page.locator('[data-testid="ec-table-card"]').textContent()
  if (
    !ecTableText?.includes('序号') ||
    !ecTableText.includes('EC编号') ||
    !ecTableText.includes('类别') ||
    !ecTableText.includes('置信度') ||
    !ecTableText.includes('名称') ||
    !ecTableText.includes('3.1.1.3') ||
    !ecTableText.includes('脂肪酶/酯酶') ||
    ecTableText.includes('列 5')
  ) {
    throw new Error(`EC markdown table header was not repaired: ${ecTableText}`)
  }

  const fragmentedTableCount = await page.locator('[data-testid="fragmented-table-card"] table').count()
  if (fragmentedTableCount !== 1) {
    throw new Error(`Fragmented markdown table did not render as one HTML table: ${fragmentedTableCount}`)
  }

  const fragmentedNestedTableCount = await page.locator('[data-testid="fragmented-table-card"] table table').count()
  if (fragmentedNestedTableCount !== 0) {
    throw new Error(`Fragmented markdown table rendered with invalid nested tables: ${fragmentedNestedTableCount}`)
  }

  const fragmentedTableText = await page.locator('[data-testid="fragmented-table-card"]').textContent()
  if (
    !fragmentedTableText?.includes('维度') ||
    !fragmentedTableText.includes('当前判断') ||
    !fragmentedTableText.includes('热稳定性') ||
    !fragmentedTableText.includes('酸稳定性') ||
    !fragmentedTableText.includes('可工程化表面位点') ||
    fragmentedTableText.includes('| --- | ---:')
  ) {
    throw new Error(`Fragmented markdown table content was not normalized: ${fragmentedTableText}`)
  }

  const markdownTableStyle = await page.locator('[data-testid="fragmented-table-card"] table').evaluate((table) => {
    const firstCell = table.querySelector('th,td')
    const wrapper = table.parentElement
    const tableStyle = window.getComputedStyle(table)
    const cellStyle = firstCell ? window.getComputedStyle(firstCell) : null
    const wrapperStyle = wrapper ? window.getComputedStyle(wrapper) : null
    return {
      tableWidth: tableStyle.width,
      tableMinWidth: tableStyle.minWidth,
      cellMinWidth: cellStyle?.minWidth || '',
      cellMaxWidth: cellStyle?.maxWidth || '',
      cellOverflowWrap: cellStyle?.overflowWrap || '',
      wrapperOverflowX: wrapperStyle?.overflowX || '',
    }
  })
  if (
    markdownTableStyle.wrapperOverflowX !== 'auto' ||
    markdownTableStyle.cellMinWidth === '0px' ||
    markdownTableStyle.cellMaxWidth === 'none' ||
    !['anywhere', 'break-word'].includes(markdownTableStyle.cellOverflowWrap)
  ) {
    throw new Error(`Markdown table layout is not constrained for wide report tables: ${JSON.stringify(markdownTableStyle)}`)
  }

  const expandedText = await page.locator('[data-testid="toolcall-card"]').textContent()
  if (!expandedText?.includes('annotation_bundle') || !expandedText.includes('Complete') || !expandedText.includes('Degraded')) {
    throw new Error(`Unexpected tool card content: ${expandedText}`)
  }

  fs.mkdirSync('output/playwright', { recursive: true })
  await page.screenshot({ path: 'output/playwright/mutation-main-table-smoke.png', fullPage: true })

  console.log('Smoke check passed')
} finally {
  await browser.close()
}
