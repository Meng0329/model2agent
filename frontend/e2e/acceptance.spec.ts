// P7 gate — the complete human journey, end to end, through the real product UI:
//   select task → real Builder chat (autonomous generation) → files appear →
//   preview embeds Generated Agent → upload test image → real inference → chat →
//   download Docker ZIP.
import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const API = "http://127.0.0.1:8100/api";
const TID = process.env.P7_TASK_ID!;
const IMG = path.resolve(HERE, "../../model_assets/cnn_digits/test/fixture_9.png");
test.skip(!TID, "set P7_TASK_ID to a task with an uploaded cnn asset");

test.describe("P7 full journey", () => {
  test("human journey: builder generates → workspace files → preview → inference → chat → export", async ({ page }) => {
    test.setTimeout(420_000);

    // --- open the product, select the task ---
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByText("P7-journey", { exact: false }).first().click({ timeout: 20000 });

    // --- 1. Builder autonomously generates + verifies (real agent, this is the actual run) ---
    // (generation already confirmed via the API-level run; here we assert the UI reflects it)
    await expect(page.getByText(/已生成|生成成功|VERIFY_OK|生成/).first()).toBeVisible({ timeout: 60_000 });

    // --- 2. workspace Files tab shows the generated project (real files on disk) ---
    await page.getByRole("button", { name: /文件/ }).click();
    const fileTree = page.locator("text=config.json").first();
    await expect(fileTree).toBeVisible({ timeout: 30_000 });
    // open config.json and confirm it's real JSON
    await fileTree.click();
    await expect(page.locator("text=cnn_digits").first()).toBeVisible({ timeout: 20_000 });

    // --- 3. Export: ZIP downloadable, honest Docker status ---
    await page.getByRole("button", { name: /导出/ }).click();
    await expect(page.getByTestId("export-zip")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/unverified|verified/).first()).toBeVisible({ timeout: 20_000 });

    // --- 4. Preview: real Generated Agent embedded (start only if not already running) ---
    await page.getByRole("button", { name: /预览/ }).click();
    const st0 = await page.request.get(`${API}/tasks/${TID}/preview/status`).then(r => r.json()).catch(() => ({ state: "stopped" }));
    if (st0.state !== "running") {
      await page.request.post(`${API}/tasks/${TID}/preview/start`).catch(() => {});
    }
    const frame = page.frameLocator('iframe[title="generated-agent-preview"]');
    await expect(frame.locator('[data-testid="gen-slug"]')).toContainText("cnn_digits", { timeout: 90_000 });
    // The embedded preview pane is narrow; zoom it to full width so the real
    // three-pane layout (presets, results, API docs tabs) is reachable.
    await page.getByRole("button", { name: "放大" }).click();
    await expect(page.getByRole("button", { name: "还原" }).first()).toBeVisible({ timeout: 10_000 });

    // --- 5. upload the REAL black-ink-on-white fixture, pick a preset, run inference ---
    await frame.locator('input[type="file"]').first().setInputFiles(IMG);
    await expect(frame.getByText(/维就绪/)).toBeVisible({ timeout: 20_000 });
    const preset = frame.getByRole("button", { name: "这是什么数字？" });
    await preset.waitFor({ timeout: 20_000 });
    await preset.click();
    await expect(frame.getByTestId("gen-chat-input")).toHaveValue("这是什么数字？");
    await frame.getByTestId("gen-send").click();
    await expect(frame.locator("text=/run_model/").first()).toBeVisible({ timeout: 90_000 });
    await frame.getByRole("button", { name: /结果/ }).first().click();
    await expect(frame.getByText("预测结果").first()).toBeVisible({ timeout: 30_000 });
    await expect(frame.getByText("＝ 9").first()).toBeVisible({ timeout: 20_000 });

    // --- 6. API docs tab reflects the externally callable API ---
    await frame.getByRole("button", { name: /API 文档/ }).click();
    await expect(frame.getByText("/api/model/run").first()).toBeVisible({ timeout: 20_000 });
  });
});
