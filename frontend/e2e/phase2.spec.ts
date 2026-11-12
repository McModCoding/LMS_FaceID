import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const evidence = path.resolve('../docs/evidence/phase2')
const run = Date.now().toString(36)
type Headers = { Authorization: string }
async function auth(request: APIRequestContext, username: string) {
  const res = await request.post('/api/v1/auth/login', { data: { username, password: 'Demo@123' } })
  expect(res.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await res.json()).access_token}` }
}
async function login(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}
async function classPage(page: Page, role: string, tab = 'exams') {
  await page.goto(`/${role}/classes/1?tab=${tab}`)
  await expect(page.getByRole('tab', { name: tab === 'exams' ? 'Bài kiểm tra' : 'Ngân hàng câu hỏi', exact: true })).toHaveAttribute('data-state', 'active')
  await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
}
async function shot(page: Page, name: string) {
  await mkdir(evidence, { recursive: true })
  await page.getByLabel('Đang tải', { exact: true }).waitFor({ state: 'hidden' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  const dialogs = page.getByRole('dialog')
  if (await dialogs.count()) expect(await dialogs.last().evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy()
  await page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: true, animations: 'disabled' })
}
async function fixture(request: APIRequestContext, label: string, changes: Record<string, unknown> = {}, publish = true) {
  const teacher = await auth(request, 'gv001')
  const student = await auth(request, 'sv001')
  const cls = await (await request.get('/api/v1/classes/1', { headers: teacher })).json()
  const questions = []
  for (const type of ['single', 'multiple', 'true_false', 'essay']) {
    const options = type === 'essay' ? [] : [{ content: 'Phương án A', is_correct: true }, { content: 'Phương án B', is_correct: type === 'multiple' }]
    if (type === 'multiple') options.push({ content: 'Phương án C', is_correct: false })
    const response = await request.post(`/api/v1/subjects/${cls.subject_id}/questions`, { headers: teacher, data: {
      type, content: `G2 ${label} ${type} ${run}`, explanation: 'Nội dung giải thích chỉ hiện theo chính sách.', options,
    } })
    expect(response.status()).toBe(201); questions.push(await response.json())
  }
  const data = { title: `G2 ${label} ${run}`, description: 'Kiểm thử giai đoạn 2, dữ liệu thật qua API.',
    duration_min: 30, open_at: new Date(Date.now() - 60000).toISOString(), close_at: new Date(Date.now() + 3600000).toISOString(),
    max_attempts: 2, score_policy: 'highest', show_result: 'after_submit', shuffle_questions: false, shuffle_options: false,
    require_fullscreen: false, record_events: true, violation_types: ['copy'], max_violations: 0, auto_submit_on_violation: false,
    questions: questions.map(q => ({ question_id: q.id, points: '2.5' })), ...changes }
  const response = await request.post('/api/v1/classes/1/exams', { headers: teacher, data })
  expect(response.status()).toBe(201)
  const exam = await response.json()
  if (publish) expect((await request.post(`/api/v1/exams/${exam.id}/publish`, { headers: teacher })).ok()).toBeTruthy()
  return { teacher, student, exam, questions, data, subjectId: cls.subject_id }
}
async function begin(request: APIRequestContext, eid: number, headers: Headers) {
  const res = await request.post(`/api/v1/exams/${eid}/attempts`, { headers }); expect(res.ok()).toBeTruthy(); return res.json()
}
async function finish(request: APIRequestContext, attemptId: number, headers: Headers, questions: any[]) {
  for (const q of questions) expect((await request.put(`/api/v1/attempts/${attemptId}/answers/${q.id}`, { headers,
    data: q.type === 'essay' ? { essay_text: 'Đóng băng đề bảo đảm các lượt làm có cùng nội dung và đáp án.' } : { selected_option_ids: q.options.filter((o: any) => o.is_correct).map((o: any) => o.id) },
  })).status()).toBe(204)
  expect((await request.post(`/api/v1/attempts/${attemptId}/submit`, { headers })).ok()).toBeTruthy()
}

test('G2-2.1 ngân hàng bốn dạng và soạn đề trên điện thoại', async ({ page, request }) => {
  await fixture(request, 'soạn đề', {}, false)
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page, 'gv001'); await classPage(page, 'lecturer', 'questions')
  await expect(page.getByText('Tự luận · Trung bình', { exact: true }).first()).toBeVisible()
  await shot(page, 'task-2.1-bank-mobile')
  await classPage(page, 'lecturer'); await page.getByRole('button', { name: 'Tạo đề nháp', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Tên bài kiểm tra', { exact: true }).fill(`G2 soạn UI ${run}`)
  const local = (n: number) => new Date(Date.now() + n + 7 * 3600000).toISOString().slice(0, 16)
  await dialog.getByLabel('Mở lúc').fill(local(-60000)); await dialog.getByLabel('Đóng lúc').fill(local(3600000))
  await dialog.getByLabel('Thời lượng (phút)').fill('30'); await dialog.getByLabel('Số lần làm tối đa').fill('2')
  await dialog.getByRole('combobox', { name: 'Chính sách tính điểm' }).click(); await page.getByRole('option', { name: 'Điểm cao nhất' }).click()
  await shot(page, 'task-2.1-draft-form-mobile')
  await dialog.getByRole('button', { name: 'Chọn', exact: true }).first().click()
  await dialog.locator('input[id^="points-"]').fill('10')
  await dialog.getByRole('button', { name: 'Lưu đề nháp', exact: true }).click()
  await expect(page.getByRole('article', { name: `G2 soạn UI ${run}` })).toBeVisible()
  await shot(page, 'task-2.1-saved-mobile')
})

test('G2-2.2 snapshot giữ nguyên khi sửa ngân hàng và khóa đề', async ({ page, request }) => {
  const f = await fixture(request, 'snapshot')
  const attempt = await begin(request, f.exam.id, f.student)
  const q = f.questions[0]
  expect((await request.put(`/api/v1/questions/${q.id}`, { headers: f.teacher, data: {
    ...q, content: 'NGÂN HÀNG ĐÃ SỬA', options: [{ content: 'Mới', is_correct: true }, { content: 'Khác', is_correct: false }],
  } })).ok()).toBeTruthy()
  expect((await request.put(`/api/v1/exams/${f.exam.id}`, { headers: f.teacher, data: f.data })).status()).toBe(409)
  await login(page, 'gv001'); await classPage(page, 'lecturer')
  const card = page.getByRole('article', { name: f.exam.title }); await expect(card.getByRole('button', { name: 'Sửa', exact: true })).toHaveCount(0)
  await card.scrollIntoViewIfNeeded(); await shot(page, 'task-2.2-locked-desktop')
  await login(page, 'sv001'); await page.setViewportSize({ width: 375, height: 812 }); await page.goto(`/student/exams/${attempt.id}`)
  await expect(page.getByText(q.content, { exact: true })).toBeVisible(); await shot(page, 'task-2.2-frozen-mobile')
})

test('G2-2.3 công bố qua UI và thông báo dẫn đúng tab', async ({ page, request }) => {
  const f = await fixture(request, 'công bố', {}, false)
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'gv001'); await classPage(page, 'lecturer')
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Công bố', exact: true }).click()
  await shot(page, 'task-2.3-publish-confirm-mobile')
  await page.getByRole('alertdialog').getByRole('button', { name: 'Xác nhận', exact: true }).click()
  await expect(page.getByRole('article', { name: f.exam.title }).getByText(/Đã công bố/)).toBeVisible()
  const res = await request.get('/api/v1/notifications?page_size=100', { headers: f.student }); expect(res.ok()).toBeTruthy()
  const notice = (await res.json()).items.find((n: any) => n.type === 'exam_published' && n.body.includes(f.exam.title))
  expect(notice.link).toBe('/student/classes/1?tab=exams')
  await login(page, 'sv001'); await page.goto(notice.link)
  await expect(page.getByRole('tab', { name: 'Bài kiểm tra', exact: true })).toHaveAttribute('data-state', 'active')
  await expect(page.getByText(f.exam.title, { exact: true })).toBeVisible(); await shot(page, 'task-2.3-published-student-mobile')
})

test('G2-2.4 bắt đầu và reload tiếp tục cùng lượt ở 375px', async ({ page, request }) => {
  const f = await fixture(request, 'tiếp tục')
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001'); await classPage(page, 'student')
  const card = page.getByText(f.exam.title, { exact: true }).locator('..').locator('..').locator('..')
  await card.getByRole('button', { name: 'Bắt đầu làm bài', exact: true }).click()
  await shot(page, 'task-2.4-start-confirm-mobile')
  await page.getByRole('button', { name: 'Vào làm bài', exact: true }).click()
  await expect(page).toHaveURL(/student\/exams\/\d+/); const url = page.url()
  await expect(page.getByText(f.questions[0].content, { exact: true })).toBeVisible()
  await page.getByRole('radio').first().check(); await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible()
  await page.reload(); await expect(page.getByRole('radio').first()).toBeChecked(); expect(page.url()).toBe(url)
  await shot(page, 'task-2.4-resume-mobile')
  await page.getByRole('button', { name: 'Câu 2, chưa trả lời', exact: true }).click()
  await page.getByRole('checkbox').nth(0).check(); await page.getByRole('checkbox').nth(1).check()
  await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible(); await shot(page, 'task-2.4-multiple-mobile')
  await page.getByRole('button', { name: 'Câu 3, chưa trả lời', exact: true }).click()
  await page.getByRole('radio').nth(1).check(); await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible()
  await shot(page, 'task-2.4-true-false-mobile')
})

test('G2-2.5 mất mạng lưu lại, xác nhận nộp và tự nộp theo giờ server', async ({ page, request, context }) => {
  const f = await fixture(request, 'lưu nháp')
  const attempt = await begin(request, f.exam.id, f.student)
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001'); await page.goto(`/student/exams/${attempt.id}`)
  await page.getByRole('button', { name: 'Câu 4, chưa trả lời', exact: true }).click()
  await context.setOffline(true)
  await page.getByRole('textbox', { name: 'Câu trả lời câu 4' }).fill('Bài tự luận phục hồi sau mất mạng.')
  await expect(page.getByText('Chưa lưu được', { exact: true })).toBeVisible(); await shot(page, 'task-2.5-offline-mobile')
  await context.setOffline(false); await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Nộp bài', exact: true }).click(); await shot(page, 'task-2.5-submit-confirm-mobile')
  await page.getByRole('button', { name: 'Tiếp tục làm', exact: true }).click()
  await expect(page.getByRole('textbox')).toHaveValue('Bài tự luận phục hồi sau mất mạng.')
  await page.getByRole('button', { name: 'Nộp bài', exact: true }).click(); await page.getByRole('button', { name: 'Xác nhận nộp bài', exact: true }).click()
  await expect(page.getByText('Đã nộp bài', { exact: true })).toBeVisible(); await shot(page, 'task-2.5-submitted-mobile')
  const timed = await fixture(request, 'hết giờ', { close_at: new Date(Date.now() + 12000).toISOString() })
  const auto = await begin(request, timed.exam.id, timed.student)
  await page.goto(`/student/exams/${auto.id}`)
  await expect(page.getByText('Bài đã được tự động nộp', { exact: true })).toBeVisible({ timeout: 25000 })
  await shot(page, 'task-2.5-auto-deadline-mobile')
})

test('G2-2.6 giảng viên chấm tự luận và sinh viên xem điểm', async ({ page, request }) => {
  const f = await fixture(request, 'chấm bài'); const attempt = await begin(request, f.exam.id, f.student)
  await finish(request, attempt.id, f.student, f.questions)
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'gv001'); await classPage(page, 'lecturer')
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Bài làm & thống kê', exact: true }).click()
  await page.getByRole('button', { name: 'Xem / chấm bài', exact: true }).click()
  const dialog = page.getByRole('dialog').last()
  await expect(dialog.getByText('Chờ chấm tự luận', { exact: false }).first()).toBeVisible()
  await dialog.getByLabel('Điểm tự luận (0–2.5000)').fill('2')
  await dialog.getByLabel('Nhận xét', { exact: true }).fill('Lập luận đúng, cần thêm ví dụ.')
  await shot(page, 'task-2.6-grade-form-mobile')
  await dialog.getByRole('button', { name: 'Lưu điểm tự luận', exact: true }).click()
  await expect(dialog.getByText('9.50/10', { exact: true })).toBeVisible(); await shot(page, 'task-2.6-graded-mobile')
  await login(page, 'sv001'); await page.goto(`/student/exams/${attempt.id}`)
  await expect(page.getByText('9.50/10', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Xem bài làm lượt 1', exact: true }).click()
  await expect(page.getByText('Nhận xét: Lập luận đúng, cần thêm ví dụ.', { exact: true })).toBeVisible()
  await shot(page, 'task-2.6-result-mobile')
})

test('G2-2.7 ghi sự kiện thật, retry cùng ID và tự nộp theo ngưỡng', async ({ page, request }) => {
  const f = await fixture(request, 'hành vi', { max_violations: 2, auto_submit_on_violation: true })
  const attempt = await begin(request, f.exam.id, f.student)
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001'); await page.goto(`/student/exams/${attempt.id}`)
  await expect(page.getByText(f.questions[0].content, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Câu 4, chưa trả lời', exact: true }).click()
  const answer = page.getByRole('textbox'); await answer.fill('Nội dung không được lưu vào nhật ký.')
  await answer.press('Control+a'); await answer.press('Control+c')
  await expect.poll(async () => (await (await request.get(`/api/v1/attempts/${attempt.id}`, { headers: f.student })).json()).violation_count).toBe(1)
  await shot(page, 'task-2.7-event-count-mobile')
  const eventId = crypto.randomUUID()
  const receipt = await request.post(`/api/v1/attempts/${attempt.id}/events`, { headers: f.student, data: { event_id: eventId, type: 'copy' } })
  expect(receipt.ok()).toBeTruthy()
  const retry = await request.post(`/api/v1/attempts/${attempt.id}/events`, { headers: f.student, data: { event_id: eventId, type: 'copy' } })
  expect((await retry.json()).violation_count).toBe(2)
  await page.reload(); await expect(page.getByText('Bài đã được tự động nộp', { exact: true })).toBeVisible()
  await shot(page, 'task-2.7-threshold-mobile')
  await login(page, 'gv001'); await classPage(page, 'lecturer')
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Bài làm & thống kê', exact: true }).click()
  await page.getByRole('button', { name: 'Xem / chấm bài', exact: true }).click()
  const dialog = page.getByRole('dialog').last(); await dialog.getByRole('heading', { name: 'Nhật ký hành vi' }).scrollIntoViewIfNeeded()
  await shot(page, 'task-2.7-event-history-mobile')
})

test('G2-2.8 thống kê Excel, chính sách kết quả và responsive sáng tối', async ({ page, request }) => {
  const f = await fixture(request, 'thống kê', { show_result: 'after_close' }); const attempt = await begin(request, f.exam.id, f.student)
  await finish(request, attempt.id, f.student, f.questions)
  expect((await request.post(`/api/v1/attempts/${attempt.id}/questions/${f.questions[3].id}/grade`, { headers: f.teacher, data: { score: '2' } })).ok()).toBeTruthy()
  await login(page, 'gv001'); await classPage(page, 'lecturer')
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Bài làm & thống kê', exact: true }).click()
  await expect(page.getByText('9.50', { exact: true }).first()).toBeVisible()
  for (const width of [375, 640, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 }); await shot(page, `task-2.8-stats-${width}-light`)
  }
  await page.evaluate(() => { document.documentElement.classList.add('dark') }); await page.setViewportSize({ width: 375, height: 812 })
  await shot(page, 'task-2.8-stats-375-dark')
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Xuất Excel', exact: true }).click()
  const file = await download; await file.saveAs(path.join(evidence, 'exam-results.xlsx'))
  await login(page, 'sv001'); await page.goto(`/student/exams/${attempt.id}`)
  await expect(page.getByText('Kết quả được hiển thị sau khi đề đóng.', { exact: true })).toBeVisible()
  await shot(page, 'task-2.8-hidden-after-close-mobile')
  expect((await request.post(`/api/v1/exams/${f.exam.id}/close`, { headers: f.teacher })).ok()).toBeTruthy()
  await page.reload(); await expect(page.getByText('9.50/10', { exact: true }).first()).toBeVisible(); await shot(page, 'task-2.8-visible-after-close-mobile')
  const hidden = await fixture(request, 'ẩn kết quả', { show_result: 'never' }); const own = await begin(request, hidden.exam.id, hidden.student)
  await finish(request, own.id, hidden.student, hidden.questions); await page.goto(`/student/exams/${own.id}`)
  await expect(page.getByText('Giảng viên không cho hiển thị kết quả.', { exact: true })).toBeVisible()
  await shot(page, 'task-2.8-never-mobile')
  const stats = await (await request.get(`/api/v1/exams/${f.exam.id}/stats`, { headers: f.teacher })).json()
  await writeFile(path.join(evidence, 'statistics-result.json'), JSON.stringify(stats, null, 2))
})

test('G2 bổ sung trạng thái tải lỗi, toàn màn hình không hỗ trợ và đóng sớm', async ({ page, request }) => {
  const f = await fixture(request, 'toàn màn hình', { require_fullscreen: true })
  await page.setViewportSize({ width: 375, height: 812 }); await login(page, 'sv001')
  let release: () => void = () => undefined
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/classes/1/student-exams**', async route => { await gate; await route.continue() })
  await page.goto('/student/classes/1?tab=exams')
  await expect(page.getByLabel('Đang tải bài kiểm tra', { exact: true })).toBeVisible()
  await shot(page, 'task-2.4-loading-mobile'); release()
  await expect(page.getByText(f.exam.title, { exact: true })).toBeVisible()
  await page.unroute('**/classes/1/student-exams**')
  await page.route('**/classes/1/student-exams**', route => route.abort('failed'))
  await page.getByRole('button', { name: 'Cập nhật trạng thái', exact: true }).click()
  await expect(page.getByText('Không tải được bài kiểm tra', { exact: true })).toBeVisible()
  await shot(page, 'task-2.4-error-mobile')
  await page.unroute('**/classes/1/student-exams**'); await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
  const card = page.getByText(f.exam.title, { exact: true }).locator('..').locator('..').locator('..')
  await card.getByRole('button', { name: 'Bắt đầu làm bài', exact: true }).click()
  await expect(page.getByText(/Ghi nhận ẩn tab, mất tiêu điểm/)).toBeVisible()
  await shot(page, 'task-2.4-behavior-disclosure-mobile')
  await page.evaluate(() => { Object.defineProperty(document.documentElement, 'requestFullscreen', { configurable: true, value: undefined }) })
  await page.getByRole('button', { name: 'Vào làm bài', exact: true }).click()
  await expect(page).toHaveURL(/\/student\/exams\/\d+$/)
  await expect(page.getByText('Trình duyệt không hỗ trợ toàn màn hình. Bạn vẫn có thể tiếp tục làm bài.', { exact: true })).toBeVisible()
  await shot(page, 'task-2.4-fullscreen-fallback-mobile')
  const aid = Number(page.url().split('/').pop())
  await login(page, 'gv001'); await classPage(page, 'lecturer')
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Đổi giờ đóng', exact: true }).click()
  const newClose = new Date(Date.now() + 600000 + 7 * 3600000).toISOString().slice(0, 16)
  await page.getByLabel('Giờ đóng mới', { exact: true }).fill(newClose)
  await shot(page, 'task-2.3-close-time-mobile')
  await page.getByRole('alertdialog').getByRole('button', { name: 'Xác nhận', exact: true }).click()
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  const changed = await (await request.get(`/api/v1/attempts/${aid}`, { headers: f.student })).json()
  expect(Date.parse(changed.deadline_at)).toBe(Date.parse(`${newClose}:00+07:00`))
  await page.getByRole('article', { name: f.exam.title }).getByRole('button', { name: 'Đóng đề', exact: true }).click()
  await shot(page, 'task-2.3-close-confirm-mobile')
  await page.getByRole('alertdialog').getByRole('button', { name: 'Xác nhận', exact: true }).click()
  await expect(page.getByRole('article', { name: f.exam.title }).getByText(/Đã đóng/)).toBeVisible()
  const closed = await (await request.get(`/api/v1/attempts/${aid}`, { headers: f.student })).json()
  expect(closed.is_auto_submitted).toBe(true)
})
