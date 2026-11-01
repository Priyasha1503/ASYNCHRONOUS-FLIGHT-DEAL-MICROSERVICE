// Visual pass: desktop + mobile screenshots, real register flow through the UI, console errors.
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://host.docker.internal:3000";
const OUT = "/out";
const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const problems = [];

const browser = await chromium.launch();
const t0 = Date.now();
for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport, colorScheme: scheme, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    page.on("console", (m) => m.type() === "error" && problems.push(`${vpName}/${scheme} console: ${m.text()}`));
    page.on("pageerror", (e) => problems.push(`${vpName}/${scheme} pageerror: ${e.message}`));
    page.on("response", (r) => r.status() >= 500 && problems.push(`${vpName}/${scheme} ${r.status()} ${r.url()}`));

    const tag = `${vpName}-${scheme}`;
    await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
    // Horizontal overflow check
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 0) problems.push(`${tag} landing horizontal overflow ${overflow}px`);
    await page.screenshot({ path: `${OUT}/landing-${tag}.png`, fullPage: true });

    if (scheme === "light") {
      if (vpName === "mobile") {
        await page.getByRole("button", { name: "Open menu" }).click();
        await page.screenshot({ path: `${OUT}/menu-${tag}.png` });
      }
      await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
      // Hydrated once the header's auth area has resolved /me (skeleton replaced by links).
      await page.getByRole("link", { name: "Sign in" }).first().waitFor({ timeout: 30000 });
      // Client-side validation
      await page.getByRole("button", { name: "Create account" }).click();
      await page.screenshot({ path: `${OUT}/register-errors-${tag}.png`, fullPage: true });
      // Real registration through the UI
      await page.getByLabel("Name (optional)").fill("Visual QA");
      await page.getByLabel("Email").fill(`qa-${vpName}-${Date.now()}@example.com`);
      await page.getByLabel("Password").fill("correct-horse-battery");
      await page.getByRole("button", { name: "Create account" }).click();
      await page.waitForURL("**/account", { timeout: 30000 });
      await page.getByRole("heading", { name: "Preferences" }).waitFor();
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${OUT}/account-${tag}.png`, fullPage: true });
      const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (ov > 0) problems.push(`${tag} account horizontal overflow ${ov}px`);
      // Save preferences through the UI
      await page.getByLabel("Home airport").fill("lhr");
      await page.getByRole("button", { name: "Save preferences" }).click();
      await page.getByText("Preferences saved").waitFor({ timeout: 10000 });
      if (vpName === "mobile") {
        // Delete account → home with confirmation toast
        await page.getByRole("button", { name: "Delete my account…" }).click();
        await page.getByLabel("Confirm with your password").fill("correct-horse-battery");
        await page.getByRole("button", { name: "Permanently delete" }).click();
        await page.waitForURL(`${BASE}/`, { timeout: 30000 });
        await page.getByText("Your account has been deleted").waitFor({ timeout: 10000 });
      } else {
        // Sign out → home
        await page.getByRole("button", { name: "Sign out" }).click();
        await page.waitForURL(`${BASE}/`, { timeout: 30000 });
      }
      const meStatus = await page.evaluate(async () => (await fetch("/api/v1/me")).status);
      if (meStatus !== 401) problems.push(`${tag} session still valid after sign-out/delete (${meStatus})`);
      await page.goto(`${BASE}/signin`, { waitUntil: "networkidle" });
      await page.screenshot({ path: `${OUT}/signin-${tag}.png`, fullPage: true });
    }
    await ctx.close();
  }
}
await browser.close();
console.log(`elapsed ${((Date.now() - t0) / 1000).toFixed(1)}s`);
console.log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "NO PROBLEMS DETECTED");
