import path from 'node:path'
import { expect, test } from '@playwright/test'

test('submission metadata can be imported from JSON', async ({ page }) => {
  await page.goto('#/submit')
  await page
    .locator('input[type="file"][accept*="json"]')
    .setInputFiles(path.resolve('tests/fixtures/submissions/submission.json'))
  await expect(page.getByLabel('Submission name')).toHaveValue('Example evaluated run')
  await expect(page.getByLabel('Scoring mode')).toHaveValue('execution')
  await expect(page.getByText('Imported submission.json')).toBeVisible()
})

test('browser precheck reads a result kit locally and reports actionable errors', async ({
  page,
}) => {
  await page.goto('#/submit')
  await page
    .locator('input[type="file"][accept*="zip"]')
    .setInputFiles(path.resolve('public/data/submit/result-submission-kit.zip'))
  await expect(page.getByRole('heading', { level: 2, name: '3. Validate and preview' })).toBeVisible()
  await expect(page.getByText('Submission requires changes')).toBeVisible()
  await expect(page.getByText(/No valid task results were found/)).toBeVisible()
  await expect(page.getByText(/archive remains on this device/i)).toBeVisible()
})
