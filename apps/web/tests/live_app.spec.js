import { test, expect } from '@playwright/test';

const liveApi = process.env.LIVE_API === '1';
const baseUrl = process.env.LIVE_WEB_URL || 'http://localhost:8788';
const activityId = process.env.LIVE_ACTIVITY_ID;

test.describe('live api smoke', () => {
  test.skip(!liveApi, 'Set LIVE_API=1 to run against a live server');

  test('insights pages render', async ({ page }) => {
    await page.goto(`${baseUrl}/insights/volume`);
    await expect(page.getByRole('heading')).toBeVisible();
  });

  test('activity detail renders flat pace when available', async ({ page }) => {
    test.skip(!activityId, 'Set LIVE_ACTIVITY_ID to a real activity id.');
    await page.goto(`${baseUrl}/activities/${activityId}`);
    await expect(page.getByText('Avg Flat Pace')).toBeVisible();
  });
});
