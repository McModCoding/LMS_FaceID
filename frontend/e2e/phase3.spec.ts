import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const evidence = path.resolve('../docs/evidence/phase3')
const run = Date.now().toString(36)
async function auth(request: APIRequestContext, username: string) {
  const res = await request.post('/api/v1/auth/login', { data: { username, password: 'Demo@123' } })
  expect(res.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await res.json()).access_token}` }
}
async function login(page: Page, username: string) {
  await page.goto('/login'); await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click(); await expect(page).not.toHaveURL(/\/login$/)
}
async function openBook(page: Page, role: string) {
  await page.goto(`/${role}/classes/1?tab=grades`)
  await expect(page.getByRole('heading', { name: 'Bảng điểm tổng hợp', exact: true })).toBeVisible()
  await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
}
async function shot(page: Page, name: string) {
  await mkdir(evidence, { recursive: true })
  await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  await page.screenshot({ path: path.join(evidence, name + '.png'), fullPage: true, animations: 'disabled' })
}

test('G3-3.1 cấu hình trọng số và nguồn theo lớp trên điện thoại', async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'gv001'); await openBook(page, 'lecturer')
  await page.getByLabel('Tên thành phần', { exact: true }).fill(`Điểm rà soát ${run}`)
  await page.getByLabel('Loại điểm', { exact: true }).selectOption('manual')
  await page.getByLabel('Trọng số (%)', { exact: true }).fill('0')
  await shot(page, 'task-3.1-component-form-mobile')
  await page.getByRole('button', { name: 'Lưu thành phần', exact: true }).click()
  await expect(page.getByText(`Điểm rà soát ${run} · 0%`, { exact: true })).toBeVisible()
  await page.getByLabel('Loại điểm', { exact: true }).selectOption('assignment')
  await expect(page.getByLabel('Nguồn điểm cùng lớp')).toBeEnabled()
  await shot(page, 'task-3.1-assignment-source-mobile')
  const teacher = await auth(request, 'gv001')
  const bad = await request.post('/api/v1/classes/1/gradebook/components', { headers: teacher, data: { name: 'Sai nguồn', type: 'exam', weight: 0, ref_id: 99999999 } })
  expect(bad.status()).toBe(422)
})

test('G3-3.2 tổng hợp server và Excel khớp màn hình', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001')
  const response = await request.get('/api/v1/classes/1/gradebook', { headers: teacher })
  expect(response.ok()).toBeTruthy(); const data = await response.json()
  expect(Number(data.weight_total)).toBe(100)
  for (const row of data.items) {
    const expected = row.values.reduce((sum: number, v: any) => sum + Number(v.score ?? 0) * Number(data.components.find((c: any) => c.id === v.component_id).weight) / 100, 0)
    expect(Math.abs(Number(row.total_score) - expected)).toBeLessThanOrEqual(0.05000001)
  }
  await mkdir(evidence, { recursive: true }); await writeFile(path.join(evidence, 'gradebook-result.json'), JSON.stringify(data, null, 2))
  await login(page, 'gv001'); await openBook(page, 'lecturer')
  await expect(page.getByText('Chưa có (tính 0)', { exact: true }).first()).toBeVisible()
  await shot(page, 'task-3.2-source-calculation-desktop')
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Xuất Excel', exact: true }).click()
  await (await download).saveAs(path.join(evidence, 'gradebook.xlsx'))
  await page.setViewportSize({ width: 375, height: 812 }); await shot(page, 'task-3.2-calculation-mobile')
})

test('G3-3.3 nhập tay, rà soát và công bố trên điện thoại', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001')
  const book = await (await request.get('/api/v1/classes/1/gradebook', { headers: teacher })).json()
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'gv001'); await openBook(page, 'lecturer')
  const score = page.getByRole('spinbutton', { name: `Điểm Điểm bổ sung của ${book.items[0].student_code}`, exact: true })
  await score.fill('8.25'); await score.locator('..').getByRole('button', { name: 'Lưu điểm', exact: true }).click()
  await expect(page.getByText('Điểm bổ sung: 8.25/10', { exact: true })).toBeVisible()
  await shot(page, 'task-3.3-manual-review-mobile')
  await page.getByRole('button', { name: 'Công bố bảng điểm', exact: true }).click()
  await shot(page, 'task-3.3-publish-confirm-mobile')
  await page.getByRole('button', { name: 'Xác nhận công bố', exact: true }).click()
  await expect(page.getByText('Đã công bố · Tổng trọng số: 100%', { exact: true })).toBeVisible()
  await shot(page, 'task-3.3-published-mobile')
})

test('G3-3.4 sinh viên chỉ xem điểm của mình và trạng thái chưa công bố', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001'); const student = await auth(request, 'sv001')
  const book = await (await request.get('/api/v1/classes/1/gradebook', { headers: teacher })).json()
  const c = book.components.find((c: any) => c.type === 'attendance')
  const payload = { name: c.name, weight: 9, type: c.type, ref_id: c.ref_id }
  expect((await request.put(`/api/v1/classes/1/gradebook/components/${c.id}`, { headers: teacher, data: payload })).ok()).toBeTruthy()
  const hidden = await (await request.get('/api/v1/classes/1/gradebook', { headers: student })).json()
  expect(hidden.items).toHaveLength(0)
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001'); await openBook(page, 'student')
  await expect(page.getByText('Chưa công bố', { exact: true })).toBeVisible(); await shot(page, 'task-3.4-unpublished-mobile')
  expect((await request.put(`/api/v1/classes/1/gradebook/components/${c.id}`, { headers: teacher, data: { ...payload, weight: 10 } })).ok()).toBeTruthy()
  expect((await request.post('/api/v1/classes/1/gradebook/publish', { headers: teacher })).ok()).toBeTruthy()
  await page.reload(); await expect(page.getByText('Đã công bố · Tổng trọng số: 100%', { exact: true })).toBeVisible()
  expect((await (await request.get('/api/v1/classes/1/gradebook', { headers: student })).json()).total).toBe(1)
  await shot(page, 'task-3.4-own-grades-mobile')
  await page.getByText(/^Tổng kết:/).first().scrollIntoViewIfNeeded(); await shot(page, 'task-3.4-total-score-mobile')
  await page.evaluate(() => document.documentElement.classList.add('dark')); await shot(page, 'task-3.4-own-grades-dark-mobile')
})

test('G3-3.5 dashboard sinh viên dẫn đến việc học ở mọi độ rộng', async ({ page, request }) => {
  const student = await auth(request, 'sv001')
  const data = await (await request.get('/api/v1/me/dashboard', { headers: student })).json()
  expect(data.groups.every((g: any) => g.count === g.items.length)).toBeTruthy()
  await login(page, 'sv001'); await expect(page).toHaveURL(/\/student\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Tổng quan công việc', exact: true })).toBeVisible()
  for (const width of [375, 640, 768, 1024, 1440]) { await page.setViewportSize({ width, height: 900 }); await shot(page, `task-3.5-dashboard-${width}`) }
  const task = data.groups.find((g: any) => g.items.length)?.items[0]
  if (task) { await page.getByRole('link', { name: task.title, exact: true }).first().click(); await expect(page).toHaveURL(new RegExp(task.link.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$')) }
})

test('G3-3.6 dashboard giảng viên Admin và biểu đồ sáng tối', async ({ page, request }) => {
  for (const [username, role] of [['gv001', 'lecturer'], ['admin', 'admin']] as const) {
    const headers = await auth(request, username)
    const data = await (await request.get('/api/v1/me/dashboard', { headers })).json()
    expect(data.role).toBe(role); expect(data.groups.every((g: any) => g.count === g.items.length)).toBeTruthy()
    await login(page, username); await expect(page).toHaveURL(new RegExp(`/${role}/dashboard$`))
    await page.setViewportSize({ width: 375, height: 812 }); await shot(page, `task-3.6-${role}-mobile`)
    await page.getByRole('heading', { name: 'Chuyên cần theo lớp', exact: true }).scrollIntoViewIfNeeded()
    await shot(page, `task-3.6-${role}-chart-mobile`)
    await page.evaluate(() => document.documentElement.classList.add('dark')); await shot(page, `task-3.6-${role}-dark-mobile`)
    await page.setViewportSize({ width: 1440, height: 1000 }); await shot(page, `task-3.6-${role}-desktop`)
  }
})

test('G3 trạng thái tải và lỗi mạng có hướng dẫn thử lại trên điện thoại', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001')
  let release: () => void = () => undefined
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/classes/1/gradebook?**', async route => { await gate; await route.continue() })
  await page.goto('/student/classes/1?tab=grades')
  await expect(page.getByLabel('Đang tải', { exact: true })).toBeVisible()
  await mkdir(evidence, { recursive: true }); await page.screenshot({ path: path.join(evidence, 'task-3.4-loading-mobile.png'), animations: 'disabled' })
  release(); await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
  await page.unroute('**/classes/1/gradebook?**')
  await page.route('**/classes/1/gradebook?**', route => route.abort('failed'))
  await page.reload(); await expect(page.getByRole('alert')).toBeVisible(); await shot(page, 'task-3.4-error-mobile')
  await page.unroute('**/classes/1/gradebook?**'); await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
  await expect(page.getByText('Đã công bố · Tổng trọng số: 100%', { exact: true })).toBeVisible()
})
