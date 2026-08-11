"use strict";

const fs = require("fs");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");


async function main() {
  const [edgePath, htmlPath, outputPath, widthText, heightText] = process.argv.slice(2);
  const width = Number(widthText);
  const height = Number(heightText);
  if (!edgePath || !htmlPath || !outputPath || !Number.isInteger(width) || !Number.isInteger(height)) {
    throw new Error("usage: node render_html_png_playwright.js EDGE HTML OUTPUT WIDTH HEIGHT");
  }
  if (!fs.existsSync(edgePath) || !fs.existsSync(htmlPath)) {
    throw new Error("Edge executable or HTML input does not exist");
  }

  const browser = await chromium.launch({ executablePath: edgePath, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    await page.evaluate(async () => {
      if (document.fonts && document.fonts.ready) {
        await document.fonts.ready;
      }
    });
    await page.screenshot({ path: outputPath, fullPage: false });
  } finally {
    await browser.close();
  }

  const stats = fs.statSync(outputPath);
  if (!stats.isFile() || stats.size <= 1024) {
    throw new Error("PNG output is missing or too small");
  }
}


main().catch((error) => {
  process.stderr.write(`${error && error.stack ? error.stack : error}\n`);
  process.exitCode = 1;
});
