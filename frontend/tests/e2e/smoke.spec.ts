import { expect, test } from '@playwright/test';

test('app shell loads with navigation and chat panel', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Suppliers' })).toBeVisible();
  await expect(page.getByLabel('chat panel')).toBeVisible();
  await expect(page.getByLabel('chat input')).toBeVisible();
});
