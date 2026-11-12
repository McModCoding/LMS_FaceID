import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
const evidence = path.resolve('../docs/evidence/ui-redesign')
for (const role of ['student', 'lecturer', 'admin'] as const) {
  test(`${role}: tổng quan lớp, bài tập và bảng điểm`, async ({ page }) => {
    await mkdir(evidence, { recursive: true })
    await page.goto('/login')
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill(role === 'student' ? 'sv001' : role === 'lecturer' ? 'gv001' : 'admin')
    await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/${role}/dashboard`))
    await page.goto(`/${role}/classes/1`)
    await expect(page.getByRole('heading', { name: 'Học liệu gần đây' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Thông báo mới' })).toBeVisible()
    await expect(page.locator('.animate-pulse')).toHaveCount(0)
    await page.screenshot({ path: path.join(evidence, `${role}-overview-desktop.png`), fullPage: true })
    await page.setViewportSize({ width: 375, height: 812 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: path.join(evidence, `${role}-overview-mobile.png`), fullPage: true })
    await page.getByRole('button', { name: 'Học tập', exact: true }).click()
    await page.getByLabel('Mục trong lớp', { exact: true }).selectOption('assignments')
    await expect(page.getByRole('heading', { name: 'Bài tập', exact: true })).toBeVisible()
    await expect(page.locator('.animate-pulse')).toHaveCount(0)
    await page.screenshot({ path: path.join(evidence, `${role}-assignments-mobile.png`), fullPage: true })
    const filter = role === 'student' ? 'todo' : 'pending'
    const [filteredResponse] = await Promise.all([
      page.waitForResponse(response => response.url().includes(`/assignments?`) && response.url().includes(`view=${filter}`)),
      page.getByRole('button', { name: role === 'student' ? 'Cần thực hiện' : 'Chờ chấm', exact: true }).click(),
    ])
    expect(filteredResponse.ok()).toBeTruthy()
    const filtered = await filteredResponse.json()
    for (const item of filtered.items) {
      if (role === 'student') expect(['open', 'late_allowed']).toContain(item.availability)
      else expect(item.pending_count).toBeGreaterThan(0)
    }
    await expect(page.locator('.animate-pulse')).toHaveCount(0)
    await page.getByRole('button', { name: 'Tất cả', exact: true }).click()
    await expect(page.locator('.animate-pulse')).toHaveCount(0)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.screenshot({ path: path.join(evidence, `${role}-assignments-desktop.png`), fullPage: true })
    await page.setViewportSize({ width: 375, height: 812 })
    await page.getByRole('button', { name: 'Đánh giá', exact: true }).click()
    await page.getByLabel('Mục trong lớp', { exact: true }).selectOption('grades')
    await expect(page.getByRole('heading', { name: 'Bảng điểm tổng hợp' })).toBeVisible()
    await expect(page.locator('.animate-pulse')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: path.join(evidence, `${role}-grades-mobile.png`), fullPage: true })
    if (role === 'student') {
      await page.getByRole('button', { name: 'Lịch & chuyên cần', exact: true }).click()
      await page.getByLabel('Mục trong lớp', { exact: true }).selectOption('attendance')
      await expect(page.getByRole('heading', { name: 'Chuyên cần của tôi' })).toBeVisible()
      await expect(page.locator('.animate-pulse')).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
      await page.screenshot({ path: path.join(evidence, 'student-attendance-mobile.png'), fullPage: true })
    }
  })
}
for (const role of ['student', 'admin'] as const) {
  test(`${role}: lớp đã đóng chỉ xem lịch sử bài tập`, async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill(role === 'student' ? 'sv001' : 'admin')
    await page.getByLabel('Mật khẩu', { exact: true }).fill('Demo@123')
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/${role}/dashboard`))
    await page.goto(`/${role}/classes/12?tab=assignments`)
    await page.getByRole('button').filter({ hasText: 'Xem bài' }).first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    if (role === 'student') await expect(dialog.getByText('Bài tập đã kết thúc, không thể nộp bài.')).toBeVisible()
    else await expect(dialog.getByRole('heading', { name: /Bài đã nộp/ })).toBeVisible()
    await expect(dialog.getByLabel('Nội dung bài làm')).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: 'Chấm bài' })).toHaveCount(0)
    await page.screenshot({ path: path.join(evidence, `${role}-closed-assignment.png`), fullPage: true })
  })
}
