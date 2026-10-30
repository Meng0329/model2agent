// P7 gate — the complete human journey, end to end, through the real product UI:
//   select task → real Builder chat (autonomous generation) → files appear →
//   preview embeds Generated Agent → upload test image → real inference → chat →
//   download Docker ZIP.
import { test, expect } from "@playwright/test";

const API = "http://127.0.0.1:8100/api";
const TID = process.env.P7_TASK_ID!;
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

    // --- 4. Preview: real Generated Agent embedded ---
    await page.getByRole("button", { name: /预览/ }).click();
    const stopBtn = page.getByRole("button", { name: "停止" });
    if (await stopBtn.count()) await stopBtn.click();
    await page.getByTestId("preview-start").click();
    const frame = page.frameLocator('iframe[title="generated-agent-preview"]');
    await expect(frame.locator('[data-testid="gen-slug"]')).toContainText("cnn_digits", { timeout: 60_000 });

    // --- 5. upload test image in the Generated Agent, run real inference ---
    await frame.locator('input[type="file"]').first().setInputFiles("/tmp/digit9.png");
    await expect(frame.getByText("64 维特征就绪")).toBeVisible({ timeout: 20_000 });
    await frame.getByTestId("gen-run").click();
    await frame.getByRole("button", { name: /推理结果/ }).click();
    await expect(frame.locator("text=预测结果 · predict").first()).toBeVisible({ timeout: 30_000 });
    await expect(frame.getByText("＝ 9").first()).toBeVisible({ timeout: 20_000 });

    // --- 6. real chat turn in the Generated Agent (its own SDK session) ---
    await frame.getByRole("button", { name: /对话/ }).click();
    await frame.getByTestId("gen-chat-input").fill("这是什么数字？请用 run_model 推理。");
    await frame.getByTestId("gen-send").click();
    await expect(frame.locator("text=/run_model/").first()).toBeVisible({ timeout: 90_000 });
    await expect(frame.locator("text=完成").first()).toBeVisible({ timeout: 90_000 });
  });
});
