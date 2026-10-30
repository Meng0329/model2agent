// P3 gate — workspace file panel syncs with real agent file writes (no full reload).
import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { join } from "path";

const ASSET_DIR = join(process.cwd(), "..", "model_assets", "cnn_digits");

test("workspace files tab shows agent-written files without reload", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /新建任务/ }).first().waitFor({ state: "visible", timeout: 15000 });

  await page.getByRole("button", { name: /新建任务/ }).first().click();
  await page.getByText("新建任务", { exact: true }).last().waitFor({ state: "visible" });
  await page.getByPlaceholder(/手写数字/).fill("P3 files");
  await page.getByPlaceholder(/希望生成的 Agent/).fill("write a file");
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

  // ask the Builder to actually create a file in project/
  await input.fill("在工作区 project/ 目录创建一个 notes.md，内容为一行注释；不要做其他事。");
  await page.getByRole("button", { name: /发送/ }).click();

  // the Files tab should reflect the new file (live-synced, no reload)
  await page.getByRole("button", { name: /文件/ }).click();
  await expect(page.getByText("notes.md")).toBeVisible({ timeout: 120000 });
  // and it should be viewable
  await page.getByText("notes.md").click();
  await expect(page.getByText(/注释|note/i).first()).toBeVisible({ timeout: 30000 });
});
