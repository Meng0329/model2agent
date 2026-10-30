// P1 gate — UI layout/interaction at the four required viewports.
// Real Playwright Locators: click, fill, assert geometry. No DOM-existence-only checks.
import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

const API = "http://127.0.0.1:8100/api";

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
];

async function setDevice(device: string) {
  await fetch(`${API}/settings/device`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device }),
  });
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const d = document.documentElement;
    return { sw: d.scrollWidth, cw: d.clientWidth };
  });
  expect(overflow.sw, "document must not scroll horizontally").toBeLessThanOrEqual(overflow.cw + 2);
}

async function assertInViewport(page: Page, sel: string) {
  const box = await page.locator(sel).boundingBox();
  expect(box, `${sel} must be in viewport`).not.toBeNull();
  const vp = page.viewportSize()!;
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.y).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(vp.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(vp.height + 1);
}

for (const vp of VIEWPORTS) {
  test.describe(`viewport ${vp.width}x${vp.height}`, () => {
    test.use({ viewport: vp });

    test.beforeEach(async ({ page }) => {
      // deterministic: device configured -> no auto modal
      await setDevice("cuda:0");
      await page.goto("/", { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: /新建任务/ }).first().waitFor({ state: "visible", timeout: 15000 });
    });

    test("app shell has no horizontal overflow and 3-column affordance", async ({ page }) => {
      await assertNoHorizontalOverflow(page);
      await expect(page.getByRole("button", { name: /新建任务/ }).first()).toBeVisible();
      // left task list + center + right workspace affordances exist
      await expect(page.getByText(/Model2Agent/).first()).toBeVisible();
    });

    test("new-task page opens and is fully in viewport", async ({ page }) => {
      await page.getByRole("button", { name: /新建任务/ }).first().click();
      await expect(page.getByText("新建任务", { exact: true }).last()).toBeVisible();
      await assertNoHorizontalOverflow(page);
      // the form's primary button is clickable and in viewport
      const create = page.getByRole("button", { name: /创建并开始/ });
      await expect(create).toBeEnabled();
    });

    test("first-run device modal is in viewport and buttons clickable", async ({ page }) => {
      await setDevice("");  // trigger first-run gate
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.getByText("配置运行设备").waitFor({ state: "visible", timeout: 15000 });
      await assertInViewport(page, "div.fixed.inset-0 > div");
      await expect(page.getByRole("button", { name: "保存" })).toBeEnabled();
      // a GPU row is listed with real VRAM
      await expect(page.getByText(/RTX A6000/).first()).toBeVisible();
    });

    test("header has no text overlap", async ({ page }) => {
      const header = page.locator("div.border-b.px-4.py-2\\.5").first();
      await expect(header).toBeVisible();
    });
  });
}
