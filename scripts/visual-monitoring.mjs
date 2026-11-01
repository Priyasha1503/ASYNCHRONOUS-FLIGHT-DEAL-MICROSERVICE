// Phase 4 browser journey against the running stack (real Celery worker, async):
// register → search → Monitor this trip (target price) → check → simulate drop → alerts →
// second user can't see the first user's monitor. Writes creds for the restart check.
//   docker run --rm --ipc=host -v "$PWD/scripts:/work" -v "$PWD/shots:/out" -w /work \
//     mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm i --no-save playwright@1.64.1 && node visual-monitoring.mjs"
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://host.docker.internal:3000";
const OUT = "/out";
const problems = [];
const log = (...a) => console.log(...a);
const t0 = Date.now();
const iso = (d) => new Date(Date.now() + d * 864e5).toISOString().slice(0, 10);
const email = `traveller-${Date.now()}@example.com`;
const password = "correct-horse-battery";

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("response", (r) => r.status() >= 500 && problems.push(`${r.status()} ${r.url()}`));

// 1. Register
await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
await page.getByRole("link", { name: "Sign in" }).first().waitFor({ timeout: 30000 });
await page.getByLabel("Name (optional)").fill("Priya");
await page.getByLabel("Email").fill(email);
await page.getByLabel("Password").fill(password);
await page.getByRole("button", { name: "Create account" }).click();
await page.waitForURL("**/account", { timeout: 30000 });
log("registered", email);

// 2. Search + 3. Monitor this trip with a target price
await page.goto(`${BASE}/search?o=LHR&d=JFK&dep=${iso(40)}&ret=${iso(47)}`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Recommended for you" }).waitFor({ timeout: 30000 });
await page.getByRole("button", { name: "Monitor this trip" }).click();
const dialog = page.getByRole("dialog", { name: "Monitor this trip" });
await dialog.waitFor();
const target = await dialog.getByLabel(/Target price/).inputValue();
log("suggested target:", target);
await page.screenshot({ path: `${OUT}/m1-dialog.png` });
await dialog.getByRole("button", { name: "Start monitoring" }).click();
await page.getByText("Monitoring started").waitFor({ timeout: 15000 });

// 4. Monitoring center → detail → check now
await page.goto(`${BASE}/monitors`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Monitoring" }).waitFor();
await page.locator("a[href^='/monitors/']").first().click();
await page.waitForURL(/\/monitors\/[0-9a-f-]{36}$/);
const monitorUrl = page.url();
// The scheduler queues the first check within ~1 min; "Check now" doesn't wait for it.
const checkNow = page.getByRole("button", { name: /Check now|Checking/ });
if (await checkNow.isEnabled()) {
  await checkNow.click();
}
await page.getByText(/^\d+ checks?\b/).first().waitFor({ timeout: 90000 });
log("first check recorded after", ((Date.now() - t0) / 1000).toFixed(1), "s");

// 5. Simulate a 25% drop → a new check → alerts. (The scheduler's own first check may also land
// meanwhile, so wait on the outcome — unread alerts — not on an exact check count.)
const checksBefore = Number((await page.getByText(/^\d+ checks?\b/).first().innerText()).match(/\d+/)[0]);
await page.getByRole("button", { name: "-25%" }).click();
const bell = page.getByRole("link", { name: /Alerts, \d+ unread/ });
for (let i = 0; i < 30 && !(await bell.isVisible()); i++) {
  await page.waitForTimeout(3000);
  await page.reload({ waitUntil: "networkidle" });
}
await bell.waitFor({ timeout: 5000 });
const checksAfter = Number((await page.getByText(/^\d+ checks?\b/).first().innerText()).match(/\d+/)[0]);
log(`checks ${checksBefore} → ${checksAfter}; bell: ${await bell.getAttribute("aria-label")}`);
if (checksAfter <= checksBefore) problems.push("simulation did not add a check");
await page.screenshot({ path: `${OUT}/m2-monitor-desktop.png`, fullPage: true });
await page.goto(`${BASE}/notifications`, { waitUntil: "networkidle" });
const titles = await page.locator("article h2").allInnerTexts();
log("alerts:", titles);
if (!titles.some((t) => /at or below your target/.test(t))) problems.push("no below-target alert");
if (!titles.some((t) => /Price drop/.test(t))) problems.push("no price-drop alert");
await page.screenshot({ path: `${OUT}/m3-alerts-desktop.png`, fullPage: true });

// Table view of the history (accessibility twin of the chart)
await page.goto(monitorUrl, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Show as table" }).click();
const rows = await page.locator("figure table tbody tr").count();
if (rows !== checksAfter && rows < checksAfter) problems.push(`history table rows = ${rows}, expected ≥ ${checksAfter}`);
log("history table rows:", rows);

// Mobile views with the same session
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: await ctx.storageState() });
const m = await mctx.newPage();
m.on("pageerror", (e) => problems.push(`mobile pageerror: ${e.message}`));
for (const [name, url] of [["m4-monitor-mobile", monitorUrl], ["m5-alerts-mobile", `${BASE}/notifications`]]) {
  await m.goto(url, { waitUntil: "networkidle" });
  await m.waitForTimeout(600);
  const px = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (px > 0) problems.push(`${name}: horizontal overflow ${px}px`);
  await m.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}
await mctx.close();

// 6. A different user cannot see it
const other = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const o = await other.newPage();
await o.goto(`${BASE}/register`, { waitUntil: "networkidle" });
await o.getByRole("link", { name: "Sign in" }).first().waitFor({ timeout: 30000 });
await o.getByLabel("Email").fill(`intruder-${Date.now()}@example.com`);
await o.getByLabel("Password").fill(password);
await o.getByRole("button", { name: "Create account" }).click();
await o.waitForURL("**/account", { timeout: 30000 });
await o.goto(monitorUrl, { waitUntil: "networkidle" });
await o.getByText("This monitor doesn't exist or isn't yours.").waitFor({ timeout: 15000 });
log("second user blocked from", monitorUrl.replace(BASE, ""));
await other.close();

writeFileSync(`${OUT}/creds.json`, JSON.stringify({ email, password, monitorUrl: monitorUrl.replace(BASE, "") }));
await browser.close();
log(`elapsed ${((Date.now() - t0) / 1000).toFixed(1)}s`);
log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "NO PROBLEMS DETECTED");
