// P2 gate — real builder chat through the browser: streamed text, tool cards, completion.
// Drives the actual UI: upload real assets, create task, send a message, assert live stream.
import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { join } from "path";

const ASSET_DIR = join(process.cwd(), "..", "model_assets", "cnn_digits");

test("real builder run streams text + tool cards and completes", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /新建任务/ }).first().waitFor({ state: "visible", timeout: 15000 });

  // create task through the UI
  await page.getByRole("button", { name: /新建任务/ }).first().click();
  await page.getByText("新建任务", { exact: true }).last().waitFor({ state: "visible" });
  await page.getByPlaceholder(/手写数字/).fill("P2 UI chat");
  await page.getByPlaceholder(/希望生成的 Agent/).fill("analyze only");

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles([
    { name: "manifest.json", mimeType: "application/json", buffer: readFileSync(join(ASSET_DIR, "manifest.json")) },
    { name: "infer.py", mimeType: "text/x-python", buffer: readFileSync(join(ASSET_DIR, "infer.py")) },
    { name: "examples.json", mimeType: "application/json", buffer: readFileSync(join(ASSET_DIR, "examples.json")) },
    { name: "model_card.md", mimeType: "text/markdown", buffer: readFileSync(join(ASSET_DIR, "model_card.md")) },
    { name: "cnn_state.pt", mimeType: "application/octet-stream", buffer: readFileSync(join(ASSET_DIR, "cnn_state.pt")) },
  ]);

  await page.getByRole("button", { name: /创建并开始/ }).click();

  const input = page.getByPlaceholder(/描述你的需求/);
  await input.waitFor({ state: "visible", timeout: 20000 });

  await input.fill("只做分析：用一句话说明这个模型资产的输入类型，不要写文件。");
  await page.getByRole("button", { name: /发送/ }).click();

  // real streamed text appears
  await expect(page.getByText(/向量|灰度|输入|模型资产/i).first()).toBeVisible({ timeout: 90000 });
  // a tool card resolves to 完成 (not stuck running)
  await expect(page.getByText("完成").first()).toBeVisible({ timeout: 90000 });
  // run completes -> UI returns to idle: 发送 button is visible again (not 停止)
  await expect(page.getByRole("button", { name: /发送/ })).toBeVisible({ timeout: 120000 });
});
