/**
 * S152 walkthrough @theme_subscription — a visitor picks a plan from a themed CMS page
 * (TariffPlanCollection) → "Select plan" opens the themed `/checkout` with that plan →
 * signs in inline and pays by invoice → the confirmation says the payment is pending →
 * once the merchant books the payment, the plans page marks the buyer's current plan
 * (a personalised region).
 *
 * Seeds (admin API, removed afterwards): two plans, a CMS page whose layout holds a
 * TariffPlanCollection showing them, and a fresh buyer (force-deleted with its invoice
 * and subscription before the plans go).
 */
import { test, expect } from '@playwright/test';
import { CmsAdminFixtures, uniqueSlug } from '@fe-user-e2e/frontend-mode/frontend-mode-support';
import {
  AdminSeeder,
  CONFIRMATION_URL_PATTERN,
  WalkthroughSteps,
  invoiceIdFromConfirmationUrl,
  seedTariffPlan,
  skipUnlessThemeMode,
  type WalkthroughBuyer,
} from '../../../theme/tests/e2e/support/walkthrough-support';

const CURRENT_PLAN_CLASS = /tariff-plan-card--current/;

test.describe('Walkthrough @theme_subscription — plans page, select, checkout, pending, current plan', () => {
  skipUnlessThemeMode(test);

  const steps = new WalkthroughSteps('theme_subscription');
  let seeder: AdminSeeder;
  let starterPlan: Record<string, any>;
  let teamPlan: Record<string, any>;
  let plansPageSlug: string;
  let buyer: WalkthroughBuyer;

  test.beforeAll(async () => {
    seeder = await AdminSeeder.open();
    starterPlan = await seedTariffPlan(seeder, uniqueSlug('Walkthrough Starter'), 15);
    teamPlan = await seedTariffPlan(seeder, uniqueSlug('Walkthrough Team'), 45);
    const collection = await seeder.create(
      '/api/v1/admin/cms/widgets',
      {
        name: uniqueSlug('Walkthrough plans'),
        slug: uniqueSlug('walkthrough-plans'),
        widget_type: 'vue-component',
        content_json: { component: 'TariffPlanCollection' },
        config: {
          component_name: 'TariffPlanCollection',
          source_mode: 'slugs',
          plan_slugs: [starterPlan.slug, teamPlan.slug],
          heading: 'Walkthrough plans',
          highlight_slug: teamPlan.slug,
        },
      },
      (widget) => `/api/v1/admin/cms/widgets/${widget.id}`,
    );
    // Registered after the widget: cleanup is LIFO, so the page and layout go before it.
    const cms = new CmsAdminFixtures(seeder.request, seeder.adminToken);
    seeder.onCleanup(() => cms.cleanup());
    const layout = await cms.layout(
      [
        { name: 'content', type: 'content' },
        { name: 'plans', type: 'vue' },
      ],
      [{ widget_id: collection.id, area_name: 'plans', sort_order: 0 }],
    );
    plansPageSlug = (await cms.post({ layout_id: layout.id, content_html: '<p>Choose the plan that fits.</p>' })).slug;
    buyer = await seeder.freshBuyer();
  });

  test.afterAll(async () => {
    await seeder?.cleanup();
  });

  test('a visitor subscribes from the plans page and sees the plan marked as current @theme_subscription', async ({ page }) => {
    await page.goto(`/${plansPageSlug}`);
    await expect(page.locator(`[data-testid="tariff-plan-card-${starterPlan.slug}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="tariff-plan-card-${teamPlan.slug}"] [data-testid="tariff-plan-badge"]`)).toBeVisible();
    await steps.themed(page, '01-plans-page');

    await page.click(`[data-testid="select-plan-${starterPlan.slug}"]`);
    await page.waitForURL(new RegExp(`/checkout\\?tarif_plan_id=${starterPlan.slug}`));
    await expect(page.locator('[data-testid="order-summary"]')).toContainText(starterPlan.name);
    await steps.themed(page, '02-checkout-with-plan');

    await page.fill('[data-testid="email-input"]', buyer.email);
    await page.fill('[data-testid="email-existing-user"] [data-testid="password-input"]', buyer.password);
    await page.click('[data-testid="email-existing-user"] [data-testid="login-button"]');
    await expect(page.locator('[data-testid="logged-in-email"]')).toContainText(buyer.email);
    await page.fill('[data-testid="billing-first-name"]', 'Walk');
    await page.fill('[data-testid="billing-last-name"]', 'Subscriber');
    await page.fill('[data-testid="billing-street"]', '4 Plan Road');
    await page.fill('[data-testid="billing-city"]', 'Cologne');
    await page.fill('[data-testid="billing-zip"]', '50667');
    await page.locator('[data-testid="billing-country"]').selectOption({ index: 1 });
    await page.locator('[data-testid="payment-method-invoice"]').click();
    await page.locator('[data-testid="terms-checkbox"] input[type="checkbox"]').check();
    await expect(page.locator('[data-testid="confirm-checkout"]')).toBeEnabled();
    await steps.themed(page, '03-signed-in-ready');
    await page.click('[data-testid="confirm-checkout"]');

    await page.waitForURL(CONFIRMATION_URL_PATTERN);
    await expect(page.locator('[data-testid="confirmation-banner"]')).toHaveClass(/confirmation-banner--pending/);
    await expect(page.locator('[data-testid="line-item-row"]').first()).toContainText(starterPlan.name);
    await steps.themed(page, '04-confirmation-pending');

    await seeder.markInvoicePaid(invoiceIdFromConfirmationUrl(page.url()));
    await page.goto(`/${plansPageSlug}`);
    await expect(page.locator(`[data-testid="tariff-plan-card-${starterPlan.slug}"]`)).toHaveClass(CURRENT_PLAN_CLASS);
    await expect(page.locator(`[data-testid="tariff-plan-card-${teamPlan.slug}"]`)).not.toHaveClass(CURRENT_PLAN_CLASS);
    await steps.themed(page, '05-current-plan-highlighted');
  });
});
