import { expect, test } from '@playwright/test';

// The preview server has no backend behind it; stub the same-origin API so the
// authenticated shell can render. Unauthenticated visits must land on /login.
const USER = { id: 'u1', username: 'alice', role: 'planner' };

test('unauthenticated visit shows the login screen, not the app shell', async ({ page }) => {
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 401, body: '' }));
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
});

test('authenticated app shell loads with navigation and chat panel', async ({ page }) => {
  await page.route('**/api/v1/auth/*', (route) => route.fulfill({ json: USER }));
  await page.route('**/api/v1/dashboard/summary', (route) =>
    route.fulfill({
      json: {
        as_of: '2026-01-01T00:00:00Z',
        alerts: { critical: 0, high: 0, medium: 0 },
        expected_loss_at_risk: { amount: '0.00', label: 'estimate' },
        data_quality: { score: 0, critical_issues: 0, warnings: 0 },
        pending_recommendations: 0,
      },
    }),
  );
  await page.route('**/api/v1/chat/ask', (route) =>
    route.fulfill({
      json: {
        intent: 'unknown',
        entity: null,
        facts: {},
        table: [],
        supported_questions: ['How is item X doing?'],
      },
    }),
  );

  await page.goto('/');

  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Suppliers' })).toBeVisible();
  await expect(page.getByLabel('chat panel')).toBeVisible();
  await expect(page.getByLabel('chat input')).toBeVisible();
});
