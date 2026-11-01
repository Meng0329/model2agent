import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.GEN_BASE || "http://127.0.0.1:7862";
const IMG = path.resolve(HERE, "../../../model_assets/cnn_digits/test/fixture_9.png");

test("generated agent: three-pane UI + preset question + real inference + api docs", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("gen-slug")).toContainText("cnn_digits", { timeout: 15000 });

  // left conversation list present
  await expect(page.getByText("会话").first()).toBeVisible({ timeout: 15000 });

  // 1) upload the REAL black-ink-on-white digit fixture (polarity fix is asserted)
  await page.locator('input[type="file"]').first().setInputFiles(IMG);
  await expect(page.getByText(/维就绪/)).toBeVisible({ timeout: 20000 });

  // 2) pick a preset question (exactly 3 chips) and send the fused input
  await page.getByRole("button", { name: "这是什么数字？" }).click();
  await expect(page.getByTestId("gen-chat-input")).toHaveValue("这是什么数字？");
  await page.getByTestId("gen-send").click();
  await expect(page.getByText(/run_model/).first()).toBeVisible({ timeout: 90000 });
  await expect(page.getByText("完成").first()).toBeVisible({ timeout: 90000 });

  // 3) real inference result in the right pane
  await page.getByRole("button", { name: /结果/ }).first().click();
  await expect(page.getByText("预测结果").first()).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("＝ 9").first()).toBeVisible({ timeout: 20000 });

  // 4) API docs tab (externally callable API)
  await page.getByRole("button", { name: /API 文档/ }).click();
  await expect(page.getByText(/\/api\/model\/run/).first()).toBeVisible({ timeout: 15000 });
});

test("generated agent: xgb tabular CSV upload + preset question", async ({ page }) => {
  const xbase = process.env.GEN_BASE_XGB;
  if (!xbase) {
    test.skip(true, "GEN_BASE_XGB not set");
    return;
  }
  const CSV = path.resolve(HERE, "../../../model_assets/xgb_tabular/test/fixture.csv");
  await page.goto(xbase, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("gen-slug")).toContainText("xgb_tabular", { timeout: 15000 });
  await page.locator('input[type="file"]').first().setInputFiles(CSV);
  await expect(page.getByText(/行 × 30 列/)).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "这张样本的预测结果是什么？" }).click();
  await page.getByTestId("gen-send").click();
  await expect(page.getByText(/run_model/).first()).toBeVisible({ timeout: 90000 });
  await page.getByRole("button", { name: /结果/ }).first().click();
  await expect(page.getByText("预测结果").first()).toBeVisible({ timeout: 20000 });
});

// Regression: in a narrow embed (e.g. the Builder preview pane) the side panes
// must auto-collapse so the composer/presets are never overlapped by the right
// panel. Guarded by the ResizeObserver that only observes once cfg has loaded.
test("generated agent: narrow embed collapses side panes, presets still clickable", async ({ page }) => {
  await page.setViewportSize({ width: 440, height: 700 });
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("gen-slug")).toContainText("cnn_digits", { timeout: 15000 });
  // side panes collapsed at 440px: the conversation list and right tabs are hidden
  await expect(page.getByText("会话").first()).toBeHidden({ timeout: 15000 });
  await page.locator('input[type="file"]').first().setInputFiles(IMG);
  await expect(page.getByText(/维就绪/)).toBeVisible({ timeout: 20000 });
  const preset = page.getByRole("button", { name: "这是什么数字？" });
  await preset.waitFor({ timeout: 10000 });
  await preset.click({ timeout: 10000 });
  await expect(page.getByTestId("gen-chat-input")).toHaveValue("这是什么数字？");
});
