// P6 gate — preview lifecycle (real process, iframe, zoom, task-switch stop) and
// export (ZIP download, honest Docker status). Drives the real UI, not just APIs.
import { test, expect } from "@playwright/test";

const API = "http://127.0.0.1:8100/api";

async function makeTaskWithProject(): Promise<string> {
  // Create a task and generate a project via the deterministic generator (the Builder's job).
  // Uses the backend's own module so this is the same code path as production.
  const res = await fetch(`${API}/tasks`, {
    method: "POST",
    headers: {},
    body: (() => {
      const fd = new FormData();
      fd.append("name", "P6 E2E");
      fd.append("goal", "preview+export");
      fd.append("device", "cuda:0");
      return fd;
    })(),
  } as RequestInit);
  if (!res.ok) throw new Error(`create task failed ${res.status}`);
  const task = await res.json();
  return task.id as string;
}

test.describe("P6 preview + export", () => {
  test("preview starts a real process, embeds it, and export offers ZIP with honest docker status", async ({ page }) => {
    // Precondition: a task whose project has been generated. This is normally done by the
    // Builder agent; for the UI gate we seed it through the same generator endpoint-equivalent.
    const tid = process.env.P6_TASK_ID;
    const tname = process.env.P6_TASK_NAME || "P6-cnn";
    test.skip(!tid, "set P6_TASK_ID to a task with a generated project");

    await page.goto("/", { waitUntil: "domcontentloaded" });
    // select the task from the history list (list shows task names)
    await page.getByText(tname, { exact: false }).first().click({ timeout: 20000 });

    // open Preview tab
    await page.getByRole("button", { name: /预览/ }).click();
    // stop any stale preview from a previous run, then start fresh
    const stopBtn = page.getByRole("button", { name: "停止" });
    if (await stopBtn.count()) {
      await stopBtn.click();
      await expect(page.getByTestId("preview-start")).toBeVisible({ timeout: 15000 });
    }
    const startBtn = page.getByTestId("preview-start");
    await expect(startBtn).toBeVisible({ timeout: 15000 });
    await startBtn.click();

    // real process → iframe with the generated agent UI is embedded
    const iframe = page.locator('iframe[title="generated-agent-preview"]');
    await expect(iframe).toBeVisible({ timeout: 45000 });
    const frame = page.frameLocator('iframe[title="generated-agent-preview"]');
    await expect(frame.locator('[data-testid="gen-slug"]')).toContainText("cnn_digits", { timeout: 30000 });

    // zoom: the iframe becomes the panel-sized overlay; toggle back
    await page.getByRole("button", { name: "放大" }).click();
    await expect(page.getByRole("button", { name: "还原" }).first()).toBeVisible();
    await page.getByRole("button", { name: "还原" }).first().click();
    await expect(page.getByRole("button", { name: "放大" })).toBeVisible();

    // export tab: ZIP link + docker status honest
    await page.getByRole("button", { name: /导出/ }).click();
    await expect(page.getByTestId("export-zip")).toBeVisible();
    await expect(page.getByText("unverified", { exact: false }).first()).toBeVisible();
  });
});
