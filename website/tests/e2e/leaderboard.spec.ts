import { expect, test } from '@playwright/test'

test('leaderboard switches independent level rankings', async ({ page }) => {
  await page.goto('#/leaderboard')
  await expect(
    page.getByRole('heading', { level: 1, name: 'PolyCodeEval Leaderboard' }),
  ).toBeVisible()
  await expect(page.getByText('12 configurations', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'L0' }).click()
  await expect(page.getByText('4 configurations', { exact: true })).toBeVisible()
  await expect(page.getByRole('table')).toContainText('ChatDev')
  await page
    .getByRole('row', { name: /Claude Code GPT-5\.4|Codex GPT-5\.4/ })
    .first()
    .click()
  await expect(page).toHaveURL(/#\/results\?.*level=L0/)
})

test('downloads expose the result submission kit', async ({ page }) => {
  await page.goto('#/downloads')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Downloads & Result Submission' }),
  ).toBeVisible()
  await expect(page.getByText('Result Submission Kit', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Download', exact: true })).toHaveCount(3)
})
