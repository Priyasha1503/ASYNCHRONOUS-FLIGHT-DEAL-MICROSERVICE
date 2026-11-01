// Phase 3 browser pass: the real search journey through the UI, desktop + mobile.
// Run (no local Node needed):
//   docker run --rm --ipc=host -v "$PWD/scripts:/work" -v "$PWD/shots:/out" -w /work \
//     mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm i --no-save playwright@1.64.1 && node visual-search.mjs"
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://host.docker.internal:3000";
const OUT = "/out";
const problems = [];
const log = (...a) => console.log(...a);
const t0 = Date.now();

const browser = await chromium.launch();
for (const [vp, viewport] of Object.entries({
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
})) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on("console", (m) => m.type() === "error" && problems.push(`${vp} console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`${vp} pageerror: ${e.message}`));
  page.on("response", (r) => r.status() >= 500 && problems.push(`${vp} ${r.status()} ${r.url()}`));
  const overflow = async (where) => {
    const px = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (px > 0) problems.push(`${vp} ${where}: horizontal overflow ${px}px`);
  };
  const shot = (name, full = true) => page.screenshot({ path: `${OUT}/${name}-${vp}.png`, fullPage: full });

  // 1. Landing → search via the hero form
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Sign in" }).first().waitFor({ timeout: 30000 }); // hydrated
  await overflow("landing");
  await shot("s1-landing", false);
  const from = page.getByRole("combobox", { name: "From" });
  await from.click();
  await from.fill("heath");
  await page.getByRole("option", { name: /London.*LHR/ }).waitFor();
  await shot("s2-combobox", false);
  await page.keyboard.press("Enter");
  const to = page.getByRole("combobox", { name: "To" });
  await to.click();
  await to.fill("JFK");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Search flights" }).click();
  await page.waitForURL(/\/search\?/, { timeout: 30000 });
  await page.getByRole("heading", { name: "Recommended for you" }).waitFor({ timeout: 30000 });
  await page.waitForTimeout(300);
  log(vp, "results URL:", page.url().replace(BASE, ""));
  if (!(await page.getByText("Demo data.").isVisible())) problems.push(`${vp}: demo banner missing`);
  await overflow("results");
  await shot("s3-results");

  // 2. Details + sort
  await page.getByRole("button", { name: "Flight details" }).first().click();
  await page.getByRole("region", { name: "Why this ranking" }).first().waitFor();
  await shot("s4-details", false);
  await page.getByLabel("Sort by").selectOption("cheapest");
  await page.waitForURL(/sort=cheapest/);
  const prices = await page
    .locator("section[aria-labelledby=all-title] article")
    .evaluateAll((els) => els.map((e) => Number(e.getAttribute("aria-label").replace(/[^0-9.]/g, ""))));
  const ascending = prices.every((p, i) => i === 0 || prices[i - 1] <= p);
  if (!ascending) problems.push(`${vp}: cheapest sort not ascending ${prices.slice(0, 5)}`);
  log(vp, `sorted ${prices.length} offers by price, ascending=${ascending}`);

  // 3. Filter: nonstop only (sidebar on desktop, sheet on mobile)
  if (vp === "mobile") {
    await page.getByRole("button", { name: "Filters" }).click();
    await page.getByRole("dialog", { name: "Filters" }).getByLabel("Nonstop only").check();
    await page.waitForURL(/stops=0/);
    await shot("s5-filters-sheet", false);
    await page.getByRole("dialog").getByRole("button", { name: /^Show / }).click();
  } else {
    await page.getByRole("complementary", { name: "Filters" }).getByLabel("Nonstop only").check();
    await page.waitForURL(/stops=0/);
  }
  await page.waitForFunction(() => !document.querySelector("[aria-busy=true]"), null, { timeout: 30000 });
  const stopTexts = await page.locator("section[aria-labelledby=all-title] article").allInnerTexts();
  const allNonstop = stopTexts.length > 0 && stopTexts.every((t) => !/\d stops? ·/.test(t));
  if (!allNonstop) problems.push(`${vp}: nonstop filter shows flights with stops (n=${stopTexts.length})`);
  log(vp, `nonstop filter: ${stopTexts.length} offers, all nonstop=${allNonstop}`);

  // 4. Impossible budget → explanation → one-click relaxation
  const url = new URL(page.url());
  url.searchParams.set("max", "50");
  url.searchParams.delete("stops");
  await page.goto(url.toString(), { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: /None of the \d+ flights meet/ }).waitFor({ timeout: 30000 });
  await overflow("no-results");
  await shot("s6-no-results");
  await page.getByRole("button", { name: /Raise budget to/ }).click();
  await page.getByRole("heading", { name: "Recommended for you" }).waitFor({ timeout: 30000 });
  log(vp, "relaxed budget →", new URL(page.url()).searchParams.get("max"));

  // 5. Invalid link → form with explanation, not a crash
  await page.goto(`${BASE}/search?o=LHR&d=LHR&dep=2020-01-01`, { waitUntil: "networkidle" });
  await page.getByText("Some search details were missing or out of date").waitFor();
  await shot("s7-invalid-link", false);
  await ctx.close();
}
await browser.close();
log(`elapsed ${((Date.now() - t0) / 1000).toFixed(1)}s`);
log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "NO PROBLEMS DETECTED");
