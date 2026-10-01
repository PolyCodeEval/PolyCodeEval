import { expect, test } from '@playwright/test'

test('benchmark routes load under the GitHub Pages base path', async ({ page }) => {
  for (const [route, heading] of [
    ['#/', 'PolyCodeEval at a glance'],
    ['#/dataset', 'Dataset Explorer'],
    ['#/results', 'Results Explorer'],
    ['#/tasks', 'Task Explorer'],
    ['#/quality', 'Quality & Coverage'],
    ['#/statistics', 'Statistical Analysis'],
    ['#/tokens', 'Token & Cost'],
    ['#/prompts', 'Prompts & Reproduction'],
  ]) {
    await page.goto(route)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
  }
})

test('paginated tables expose 20, 50, and 100 row sizes', async ({ page }) => {
  await page.goto('#/tasks')
  const pageSize = page.getByLabel('Rows per page')
  await expect(pageSize).toBeVisible()
  await expect(pageSize.locator('option')).toHaveText(['20', '50', '100'])
})
