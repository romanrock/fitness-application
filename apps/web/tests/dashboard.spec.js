import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/health', async (route) => {
    await route.fulfill({ json: { last_update: '2026-02-01T14:12:06.216132+00:00' } });
  });
  await page.route('**/api/weekly?limit=4', async (route) => {
    await route.fulfill({ json: { weekly: [{ week: '2026-01-26' }] } });
  });
  await page.route('**/api/activity_totals**', async (route) => {
    await route.fulfill({
      json: {
        totals: [
          { activity_type: 'run', count: 4, distance_m: 25300 },
          { activity_type: 'golf', count: 1, distance_m: 0 },
          { activity_type: 'walk', count: 2, distance_m: 5200 }
        ]
      }
    });
  });
  await page.route('**/api/activities**', async (route) => {
    await route.fulfill({
      json: {
        activities: [
          { activity_id: 'run-1', activity_type: 'run', name: 'Lunch Run', start_time: '2026-02-01T12:16:07Z', distance_m: 10000, moving_s: 2753 },
          { activity_id: 'walk-1', activity_type: 'walk', name: 'Evening Walk', start_time: '2026-01-31T18:00:00Z', distance_m: 3200, moving_s: 2100 }
        ]
      }
    });
  });
});

test('dashboard summary renders', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('All Time')).toBeVisible();
  await expect(page.getByText('This Week')).toBeVisible();
  await expect(page.getByText(/Running/)).toBeVisible();
});

test('clicking Running card opens Activities tab', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Running').first().click();
  await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();
  await expect(page.getByText('All time • run')).toBeVisible();
});

test('activities list renders cards', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Activities' }).click();
  await expect(page.getByText('Lunch Run')).toBeVisible();
});
