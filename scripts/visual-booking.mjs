// Booking-link pass: observed (affiliate) fares render honestly and the Book link is correct.
// Needs a stack serving Travelpayouts-style data (real token, or the mock described in PROGRESS.md).
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://host.docker.internal:3000";
const URL_ = `${BASE}/search?o=LHR&d=JFK&dep=2026-12-10&ret=2026-12-17&near=1`;
const problems = [];
const browser = await chromium.launch();
for (const [vp, viewport] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } })) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => problems.push(`${vp} pageerror: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && problems.push(`${vp} console: ${m.text()}`));
  await page.goto(URL_, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Recommended for you" }).waitFor({ timeout: 30000 });
  if (await page.getByText("Demo data.").count()) problems.push(`${vp}: demo banner shown for real-source data`);
  const book = page.getByRole("link", { name: /Check price & book/ }).first();
  const attrs = await book.evaluate((a) => ({ href: a.href, target: a.target, rel: a.rel }));
  console.log(vp, attrs);
  if (!attrs.href.startsWith("https://www.aviasales.com/") || !attrs.href.includes("marker=")) problems.push(`${vp}: bad href`);
  if (attrs.target !== "_blank" || !/sponsored/.test(attrs.rel) || !/noopener/.test(attrs.rel)) problems.push(`${vp}: bad target/rel`);
  if (!(await page.getByText("SkyScout may earn a commission").first().isVisible())) problems.push(`${vp}: no affiliate disclosure`);
  if (!(await page.getByText("Observed").first().isVisible())) problems.push(`${vp}: no Observed label`);
  await page.getByRole("button", { name: "Flight details" }).first().click();
  await page.getByText(/doesn.t list connection airports/).first().waitFor();
  const px = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (px > 0) problems.push(`${vp}: horizontal overflow ${px}px`);
  await page.screenshot({ path: `/out/b-results-${vp}.png`, fullPage: vp === "mobile" });
  await ctx.close();
}
await browser.close();
console.log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "NO PROBLEMS DETECTED");
