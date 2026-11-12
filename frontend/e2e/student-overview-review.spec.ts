import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
const evidence = path.resolve('../docs/evidence/student-overview-review')
test('ảnh tổng quan sinh viên trước và sau', async ({ page }) => {
  await mkdir(evidence, { recursive: true })
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill('sv001')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL(/\/student\/dashboard/)
  await page.goto('/student/classes/1')
  await expect(page.getByRole('heading', { name: 'Học liệu gần đây' })).toBeVisible()
  await expect(page.locator('.animate-pulse')).toHaveCount(0)
  await expect(page.getByText('Không tải được việc học.')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Thông tin lớp' })).toBeVisible()
  await page.screenshot({ path: path.join(evidence, `${process.env.OVERVIEW_STAGE || 'after'}-desktop.png`), fullPage: true })
  await page.setViewportSize({ width: 375, height: 812 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  await page.screenshot({ path: path.join(evidence, `${process.env.OVERVIEW_STAGE || 'after'}-mobile.png`), fullPage: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.evaluate(() => document.documentElement.classList.add('dark'))
  await page.screenshot({ path: path.join(evidence, `${process.env.OVERVIEW_STAGE || 'after'}-mobile-dark.png`), fullPage: true, animations: 'disabled' })
  await page.getByRole('heading', { name: 'Thông báo lớp' }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(evidence, `${process.env.OVERVIEW_STAGE || 'after'}-mobile-lower.png`), fullPage: true, animations: 'disabled' })
})


test('lỗi lịch không che học liệu và có thể thử lại', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill('sv001')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL(/\/student\/dashboard/)
  let failSchedule = true
  await page.route('**/api/v1/classes/1/schedules', async route => {
    if (failSchedule) await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Không tải được lịch kiểm thử' }) })
    else await route.continue()
  })
  await page.goto('/student/classes/1')
  const alert = page.getByRole('alert').filter({ hasText: 'Không tải được lịch kiểm thử' })
  await expect(alert).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Học liệu gần đây' })).toBeVisible()
  failSchedule = false
  await alert.getByRole('button', { name: 'Thử lại' }).click()
  await expect(alert).toHaveCount(0)
  await expect(page.getByText('Lịch định kỳ', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Xem mục học liệu' }).click()
  await expect(page).toHaveURL(/tab=materials/)
})


test('tên dài và trạng thái không có nội dung trên điện thoại', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill('sv001')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL(/\/student\/dashboard/)
  await page.route('**/api/v1/classes/1', async route => {
    const response = await route.fetch(); const data = await response.json()
    data.subject_name = 'TênMônHọcRấtDàiKhôngCóKhoảngTrắng'.repeat(8)
    await route.fulfill({ response, json: data })
  })
  await page.route('**/api/v1/classes/1/materials?*', route => route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }))
  await page.route('**/api/v1/classes/1/announcements', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/classes/1/schedules', route => route.fulfill({ json: [] }))
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/student/classes/1')
  await expect(page.getByText('Chưa có học liệu. Giảng viên sẽ đăng tài liệu tại đây.')).toBeVisible()
  await expect(page.getByText('Chưa có thông báo trong lớp.')).toBeVisible()
  await expect(page.getByText('Chưa có lịch định kỳ. Xem danh sách buổi học để biết lịch chi tiết.')).toBeVisible()
  for (const width of [375, 640, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 812 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    const heading = page.locator('h1').first()
    expect(await heading.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy()
  }
  await page.setViewportSize({ width: 375, height: 812 })
  await page.screenshot({ path: path.join(evidence, 'after-long-title-mobile.png'), fullPage: true })
})
