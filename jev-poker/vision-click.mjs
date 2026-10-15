#!/usr/bin/env node
// Screenshot the game canvas, recognize a unique visible label with Apple Vision,
// click its current canvas-relative center, and capture the result. No cached pixels.
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import pkg from '/home/user/golden-land-new/runtime/dsh-home/profiles/web/node_modules/playwright/index.js';
const { chromium } = pkg;
const label = process.argv[2];
if (!label) throw Error('Usage: node vision-click.mjs "exact visible label"');
const base = '/home/user/jev-poker';
const browser = await chromium.connectOverCDP('http://127.0.0.1:9222', { noDefaultViewport: true });
try {
  const page = browser.contexts()[0].pages().find(p => p.url().includes('crazypanda'));
  if (!page) throw Error('CrazyPanda page unavailable');
  const canvas = page.frameLocator('#canvasiframe').locator('canvas#canvascontainer');
  const box = await canvas.boundingBox();
  if (!box) throw Error('Canvas unavailable');
  const viewport = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
  const before = `${base}/vision-before.png`, after = `${base}/vision-after.png`;
  await page.screenshot({ path: before });
  const raw = execFileSync('swift', [`${base}/vision-ocr.swift`, before], { encoding: 'utf8', timeout: 30000 });
  const ocr = JSON.parse(raw);
  const clean = s => s.toLowerCase().replace(/\s+/g, ' ').trim();
  // Prefix mode supports changing countdown suffixes, e.g. «Вернуться 00:40».
  const prefix = label.endsWith('*') ? clean(label.slice(0, -1)) : null;
  const matches = ocr.items.filter(item => (prefix ? clean(item.text).startsWith(prefix) : clean(item.text) === clean(label)) && item.confidence >= 0.45);
  if (matches.length !== 1) throw Error(`Need one '${label}' OCR match; found ${matches.length}. Candidates: ${JSON.stringify(ocr.items.filter(i => clean(i.text).includes(clean(label))))}`);
  const item = matches[0];
  // Full-page screenshot may include browser chrome/scroll; map using page screenshot
  // dimensions and the current page viewport, then subtract the live canvas box.
  const x = (item.x + item.width / 2) * viewport.width / ocr.width - box.x;
  const y = (item.y + item.height / 2) * viewport.height / ocr.height - box.y;
  console.log(JSON.stringify({ target: item, canvas: box, viewport, image: [ocr.width, ocr.height], position: { x, y } }));
  if (!(x > 5 && x < box.width-5 && y > 5 && y < box.height-5)) throw Error('Target outside canvas');
  await canvas.click({ position: { x, y } });
  await page.waitForTimeout(800);
  await page.screenshot({ path: after });
  console.log(`before=${before} after=${after}`);
} finally { await browser.close(); }
