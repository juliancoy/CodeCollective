import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  ({ chromium } = require("../portal/web/node_modules/playwright"));
}

const baseUrl = process.env.SMOKE_BASE_URL || "https://codecollective.us";
const executablePath = process.env.PLAYWRIGHT_CHROME_PATH || "/usr/bin/google-chrome";
const paths = (process.env.SMOKE_PATHS || "/,/platform.html,/calendar.html,/projects.html")
  .split(",")
  .map((path) => path.trim())
  .filter(Boolean);

const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ["--no-sandbox"],
});

try {
  for (const path of paths) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    const url = new URL(path, baseUrl).toString();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await page.waitForTimeout(1_000);

    const result = await page.evaluate(() => {
      const login = document.querySelector("#portal-login-button");
      if (!login) return { hasLogin: false };
      const rect = login.getBoundingClientRect();
      const style = window.getComputedStyle(login);
      return {
        hasLogin: true,
        text: login.textContent.trim(),
        href: login.href,
        visible: rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden",
      };
    });

    if (!result.hasLogin) {
      throw new Error(`${url}: #portal-login-button is missing`);
    }
    if (!result.visible) {
      throw new Error(`${url}: #portal-login-button is not visible`);
    }
    if (result.text !== "Login") {
      throw new Error(`${url}: expected Login text, got ${JSON.stringify(result.text)}`);
    }
    if (!result.href.startsWith("https://id.codecollective.us/app/login?")) {
      throw new Error(`${url}: unexpected login href ${result.href}`);
    }

    await page.click("#portal-login-button");
    const modalResult = await page.evaluate(() => {
      const modal = document.querySelector("#login-choice-modal");
      const google = document.querySelector('[data-login-provider="google"]');
      const github = document.querySelector('[data-login-provider="github"]');
      const password = document.querySelector('[data-login-provider="password"]');
      return {
        modalVisible: Boolean(modal && !modal.hidden),
        googleHref: google && google.href,
        githubHref: github && github.href,
        passwordHref: password && password.href,
      };
    });

    if (!modalResult.modalVisible) {
      throw new Error(`${url}: login modal did not open`);
    }
    if (!modalResult.googleHref.startsWith("https://id.codecollective.us/auth/google/login?")) {
      throw new Error(`${url}: unexpected Google login href ${modalResult.googleHref}`);
    }
    if (!modalResult.githubHref.startsWith("https://id.codecollective.us/auth/github/login?")) {
      throw new Error(`${url}: unexpected GitHub login href ${modalResult.githubHref}`);
    }
    if (!modalResult.passwordHref.startsWith("https://id.codecollective.us/app/login?")) {
      throw new Error(`${url}: unexpected password login href ${modalResult.passwordHref}`);
    }

    console.log(`${url}: login nav ok`);
    await page.close();
  }
} finally {
  await browser.close();
}
