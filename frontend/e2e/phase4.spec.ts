import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { mkdir, writeFile, readFile, copyFile } from 'node:fs/promises'
import path from 'node:path'

const evidence = path.resolve('../docs/evidence/phase4')
const run = Date.now().toString(36)
async function auth(request: APIRequestContext, username: string) {
  const res = await request.post('/api/v1/auth/login', { data: { username, password: 'Demo@123' } })
  expect(res.ok()).toBeTruthy(); return { Authorization: `Bearer ${(await res.json()).access_token}` }
}
async function login(page: Page, username: string) {
  await page.goto('/login'); await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL(/\/(admin|lecturer|student)\/dashboard$/)
}
async function ready(page: Page) {
  await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
}
async function shot(page: Page, name: string) {
  await ready(page); await mkdir(evidence, { recursive: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  const dialogs = page.getByRole('dialog')
  if (await dialogs.count()) expect(await dialogs.last().evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy()
  await page.screenshot({ path: path.join(evidence, name + '.png'), fullPage: true, animations: 'disabled' })
}

test('G4-4.1 nhật ký theo ngày Việt Nam, chi tiết và trạng thái rỗng', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001')
  expect((await request.post('/api/v1/classes/1/gradebook/publish', { headers: teacher })).ok()).toBeTruthy()
  await login(page, 'admin'); await page.goto('/admin/audit-logs'); await ready(page)
  await page.getByLabel('Thao tác', { exact: true }).selectOption('PUBLISH_GRADEBOOK')
  await expect(page.getByRole('button', { name: /Xem chi tiết nhật ký/ }).first()).toBeVisible()
  const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())
  await page.getByLabel('Từ ngày (Việt Nam)', { exact: true }).fill(date)
  await page.getByLabel('Đến hết ngày (Việt Nam)', { exact: true }).fill(date)
  await shot(page, 'task-4.1-filter-desktop')
  await page.setViewportSize({ width: 375, height: 812 }); await shot(page, 'task-4.1-filter-mobile')
  const button = page.getByRole('button', { name: /Xem chi tiết nhật ký/ }).first()
  await button.focus(); await button.press('Enter'); await expect(page.getByRole('dialog')).toBeVisible()
  await shot(page, 'task-4.1-detail-mobile'); await page.keyboard.press('Escape'); await expect(button).toBeFocused()
  await page.getByLabel('Tên đăng nhập người thực hiện').fill(`no-such-user-${run}`)
  await expect(page.getByText('Không có nhật ký phù hợp. Đổi khoảng ngày hoặc xóa bộ lọc để xem lại.', { exact: true })).toBeVisible()
  await shot(page, 'task-4.1-empty-mobile')
})

test('G4-4.2 thông số vận hành an toàn và trạng thái FaceID trung thực', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'admin'); await page.goto('/admin/system-info')
  await expect(page.getByText('Asia/Ho_Chi_Minh', { exact: true })).toBeVisible()
  await shot(page, 'task-4.2-settings-mobile')
  await page.evaluate(() => document.documentElement.classList.add('dark')); await shot(page, 'task-4.2-settings-dark-mobile')
  await page.goto('/admin/face'); await expect(page.getByRole('button', { name: 'Reindex ảnh đang chờ', exact: true })).toBeDisabled()
  await shot(page, 'task-4.2-face-not-ready-mobile')
})

test('G4-4.3 trung tâm thông báo có phân trang và đọc nội dung', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001')
  for (let i = 0; i < 22; i++) expect((await request.post('/api/v1/classes/1/announcements', { headers: teacher,
    data: { title: `M8 thông báo ${run} ${i + 1}`, content: 'Thông báo tạo qua API thật để nghiệm thu phân trang.', is_pinned: false },
  })).ok()).toBeTruthy()
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001')
  await page.getByRole('button', { name: /^Thông báo/ }).click(); await page.getByRole('menuitem', { name: 'Xem tất cả thông báo', exact: true }).click()
  await expect(page).toHaveURL(/\/student\/notifications$/); await expect(page.getByRole('button', { name: 'Trang sau', exact: true })).toBeEnabled()
  await shot(page, 'task-4.3-notifications-mobile')
  await page.getByRole('button', { name: 'Trang sau', exact: true }).click(); await ready(page); await shot(page, 'task-4.3-notifications-page2-mobile')
  const button = page.getByRole('button', { name: 'Mở nội dung', exact: true }).first()
  if (await button.count()) { await button.click(); await expect(page).toHaveURL(/\/student\/classes\/1(?:\?.*)?$/) }
})

test('G4-4.3 retry tệp sau công bố không tạo bài tập trùng', async ({ page, request }) => {
  const teacher = await auth(request, 'gv001')
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'gv001'); await page.goto('/lecturer/classes/1?tab=assignments')
  await page.getByRole('button', { name: 'Giao bài', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const title = `M8 tệp retry ${run}`
  await dialog.getByLabel('Tiêu đề', { exact: true }).fill(title)
  await dialog.getByLabel('Hạn nộp (giờ Việt Nam)', { exact: true }).fill(new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 16))
  await dialog.getByLabel('Tệp hướng dẫn (không bắt buộc)', { exact: true }).setInputFiles({ name: 'huong-dan.txt', mimeType: 'text/plain', buffer: Buffer.from('Hướng dẫn nghiệm thu M8.') })
  let failed = false
  await page.route('**/assignments/*/attachment', async route => { if (!failed) { failed = true; await route.abort('failed') } else await route.continue() })
  await dialog.getByRole('button', { name: 'Công bố bài tập', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Bài tập đã được công bố')
  await shot(page, 'task-4.3-attachment-partial-mobile')
  await dialog.getByRole('button', { name: 'Thử tải lại tệp', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  const rows = (await (await request.get('/api/v1/classes/1/assignments?page_size=100', { headers: teacher })).json()).items.filter((a: any) => a.title === title)
  expect(rows).toHaveLength(1); expect(rows[0].has_attachment).toBe(true)
  await shot(page, 'task-4.3-attachment-success-mobile')
})

test('G4-4.4 responsive sáng tối, bàn phím, tải chậm và lỗi thật', async ({ page }) => {
  await login(page, 'admin'); await page.goto('/admin/audit-logs')
  for (const width of [375, 640, 768, 1024, 1440]) { await page.setViewportSize({ width, height: 900 }); await shot(page, `task-4.4-audit-${width}-light`) }
  await page.setViewportSize({ width: 375, height: 812 }); await page.evaluate(() => document.documentElement.classList.add('dark')); await shot(page, 'task-4.4-audit-dark-mobile')
  await page.getByLabel('Từ ngày (Việt Nam)', { exact: true }).fill('2026-11-06'); await page.getByLabel('Đến hết ngày (Việt Nam)', { exact: true }).fill('2026-11-05')
  await expect(page.getByRole('alert')).toContainText('Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.')
  await shot(page, 'task-4.4-backend-error-mobile')
  await page.getByRole('button', { name: 'Xóa bộ lọc', exact: true }).click(); await ready(page)
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.evaluate(() => document.documentElement.style.fontSize = '200%'); await shot(page, 'task-4.4-text-200-percent')
  await page.evaluate(() => document.documentElement.style.fontSize = '')
  let release: () => void = () => undefined
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/admin/system-info', async route => { await gate; await route.continue() })
  await page.goto('/admin/system-info'); await expect(page.getByLabel('Đang tải', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 375, height: 812 }); await mkdir(evidence, { recursive: true })
  await page.screenshot({ path: path.join(evidence, 'task-4.4-loading-mobile.png'), animations: 'disabled' })
  release(); await expect(page.getByText('Asia/Ho_Chi_Minh', { exact: true })).toBeVisible(); await page.unroute('**/api/v1/admin/system-info')
})

test('G4-4.5 bảng điểm 60 sinh viên và bằng chứng hiệu năng', async ({ page }) => {
  const data = JSON.parse(await readFile(path.join(evidence, 'performance.json'), 'utf8'))
  expect(data.students_in_class).toBe(60); expect(data.identical_results).toBe(true)
  expect(data.after.query_max).toBeLessThan(data.before.query_min)
  await login(page, 'gv001'); await page.goto('/lecturer/classes/1?tab=grades')
  await expect(page.getByText('60 kết quả · Trang 1/3', { exact: true })).toBeVisible()
  await shot(page, 'task-4.5-gradebook-60-desktop')
  await page.setViewportSize({ width: 375, height: 812 }); await page.getByText(/^Tổng kết:/).first().scrollIntoViewIfNeeded(); await shot(page, 'task-4.5-gradebook-60-mobile')
})

test('G4-4.6 quyền Admin và không lộ thông số nhạy cảm', async ({ page, request }) => {
  const student = await auth(request, 'sv001'); const teacher = await auth(request, 'gv001')
  const results = []
  for (const headers of [student, teacher]) for (const url of ['/audit-logs', '/admin/system-info']) {
    const response = await request.get('/api/v1' + url, { headers }); expect(response.status()).toBe(403)
    results.push({ endpoint: url, status: response.status(), code: (await response.json()).detail?.code })
  }
  const noAuth = await request.get('/api/v1/admin/system-info'); expect(noAuth.status()).toBe(401)
  await mkdir(evidence, { recursive: true }); await writeFile(path.join(evidence, 'acl-results.json'), JSON.stringify({ no_auth: 401, cross_role: results }, null, 2))
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001'); await page.goto('/admin/system-info')
  await expect(page).toHaveURL(/\/student\/dashboard$/); await shot(page, 'task-4.6-student-role-guard-mobile')
  await login(page, 'admin'); await page.goto('/admin/system-info'); await expect(page.getByText('Asia/Ho_Chi_Minh', { exact: true })).toBeVisible()
  await shot(page, 'task-4.6-safe-admin-info-mobile')
})

test('G4-4.7 video demo thi, chấm và công bố điểm thật', async ({ browser, request }) => {
  const teacher = await auth(request, 'gv001'); const student = await auth(request, 'sv001')
  const assignments = (await (await request.get('/api/v1/classes/1/assignments?page_size=100', { headers: teacher })).json()).items
  const original = assignments.find((a: any) => a.title === 'Bài tập khởi động')
  const submissions = (await (await request.get(`/api/v1/assignments/${original.id}/submissions`, { headers: teacher })).json()).items
  const own = submissions.find((s: any) => s.student_code === 'SV001') || submissions[0]
  expect((await request.post(`/api/v1/submissions/${own.id}/grade`, { headers: teacher, data: { score: 7, feedback: 'Bài mẫu đạt yêu cầu cơ bản.' } })).ok()).toBeTruthy()
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5218', viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Ho_Chi_Minh', locale: 'vi-VN', recordVideo: { dir: path.resolve('../.local/phase4-video'), size: { width: 1280, height: 900 } } })
  const page = await context.newPage()
  try {
    await login(page, 'sv001')
    const exams = (await (await request.get('/api/v1/classes/1/student-exams', { headers: student })).json()).items
    const started = await request.post(`/api/v1/exams/${exams[0].id}/attempts`, { headers: student }); expect(started.ok()).toBeTruthy()
    const attempt = await started.json(); await page.goto(`/student/exams/${attempt.id}`)
    await expect(page.getByRole('radio').first()).toBeVisible(); await page.getByRole('radio').first().check()
    await page.getByRole('button', { name: /^Câu 2,/ }).click(); await page.getByRole('checkbox').nth(0).check(); await page.getByRole('checkbox').nth(1).check()
    await page.getByRole('button', { name: /^Câu 3,/ }).click(); await page.getByRole('radio').first().check()
    await page.getByRole('button', { name: /^Câu 4,/ }).click(); await page.getByRole('textbox').fill('Đóng băng đề bảo đảm nội dung và đáp án không thay đổi giữa các lượt làm.'); await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Nộp bài', exact: true }).click(); await page.getByRole('button', { name: 'Xác nhận nộp bài', exact: true }).click(); await expect(page.getByText('Đã nộp bài', { exact: true })).toBeVisible()
    await login(page, 'gv001'); await page.goto('/lecturer/classes/1?tab=exams')
    await page.getByRole('button', { name: 'Bài làm & thống kê', exact: true }).first().click(); await page.getByRole('button', { name: 'Xem / chấm bài', exact: true }).first().click()
    const review = page.getByRole('dialog').last(); await review.getByLabel('Điểm tự luận (0–2.5000)').fill('2.5'); await review.getByLabel('Nhận xét', { exact: true }).fill('Giải thích rõ vai trò snapshot.'); await review.getByRole('button', { name: 'Lưu điểm tự luận', exact: true }).click()
    await expect(review.getByText('10.00/10', { exact: true })).toBeVisible()
    await page.goto('/lecturer/classes/1?tab=grades'); await page.getByRole('button', { name: 'Công bố bảng điểm', exact: true }).click(); await page.getByRole('button', { name: 'Xác nhận công bố', exact: true }).click(); await ready(page)
    await login(page, 'sv001'); await page.goto('/student/classes/1?tab=grades'); await page.getByText(/^Tổng kết:/).scrollIntoViewIfNeeded(); await shot(page, 'task-4.7-student-final-grade-desktop')
    await login(page, 'admin'); await page.goto('/admin/audit-logs'); await page.getByLabel('Thao tác', { exact: true }).selectOption('PUBLISH_GRADEBOOK'); await ready(page); await shot(page, 'task-4.7-audit-demo-desktop')
  } finally {
    await context.close()
    const video = await page.video()?.path(); if (video) await copyFile(video, path.join(evidence, 'demo-m8.webm'))
  }
})

test('G4-4.4 lỗi tải lớp và lịch không biến thành dữ liệu rỗng', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  for (const [username, role] of [['sv001', 'student'], ['gv001', 'lecturer']] as const) {
    await login(page, username)
    await page.route('**/api/v1/classes/1', route => route.abort('failed'))
    await page.goto(`/${role}/classes/1`)
    await expect(page.getByRole('alert')).toContainText('Không thể tải thông tin lớp học.')
    await shot(page, `task-4.4-${role}-class-error-mobile`)
    await page.unroute('**/api/v1/classes/1'); await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Nhập môn Lập trình', exact: true })).toBeVisible()
    await page.route('**/api/v1/me/timetable?**', route => route.abort('failed'))
    await page.goto(`/${role}/timetable`)
    await expect(page.getByRole('alert')).toContainText('Không thể tải thời khóa biểu.')
    await shot(page, `task-4.4-${role}-timetable-error-mobile`)
    await page.unroute('**/api/v1/me/timetable?**'); await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveCount(0)
  }
})
