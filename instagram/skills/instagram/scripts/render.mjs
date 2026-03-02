import puppeteer from 'puppeteer';
import { readFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Monthly template configuration
const MONTHLY_TEMPLATES = {
  1:  { monthEn: 'January',   accentColor: '#d97706', accentBg: '#fff7ed', highlightBg: '#ffe4b5', icon: '☕' },
  2:  { monthEn: 'February',  accentColor: '#0d9488', accentBg: '#f0fdfa', highlightBg: '#ccfbf1', icon: '📖' },
  3:  { monthEn: 'March',     accentColor: '#db2777', accentBg: '#fdf2f8', highlightBg: '#fbcfe8', icon: '🌸' },
  4:  { monthEn: 'April',     accentColor: '#65a30d', accentBg: '#f7fee7', highlightBg: '#bef264', icon: '🌱' },
  5:  { monthEn: 'May',       accentColor: '#059669', accentBg: '#ecfdf5', highlightBg: '#6ee7b7', icon: '🍃' },
  6:  { monthEn: 'June',      accentColor: '#7c3aed', accentBg: '#f5f3ff', highlightBg: '#c4b5fd', icon: '💠' },
  7:  { monthEn: 'July',      accentColor: '#0ea5e9', accentBg: '#f0f9ff', highlightBg: '#7dd3fc', icon: '☀️' },
  8:  { monthEn: 'August',    accentColor: '#e11d48', accentBg: '#fff1f2', highlightBg: '#fda4af', icon: '🔥' },
  9:  { monthEn: 'September', accentColor: '#b45309', accentBg: '#fffbeb', highlightBg: '#fcd34d', icon: '🌙' },
  10: { monthEn: 'October',   accentColor: '#7e22ce', accentBg: '#faf5ff', highlightBg: '#d8b4fe', icon: '🍂' },
  11: { monthEn: 'November',  accentColor: '#9f1239', accentBg: '#fff1f2', highlightBg: '#fda4af', icon: '🪶' },
  12: { monthEn: 'December',  accentColor: '#15803d', accentBg: '#f0fdf4', highlightBg: '#86efac', icon: '❄️' },
};

async function main() {
  // Read the latest post data
  const dataPath = join(process.env.HOME, '.claude/projects/-home-stsrj/memory/instagram-latest.json');
  if (!existsSync(dataPath)) {
    console.error('Error: instagram-latest.json not found. Run /instagram first.');
    process.exit(1);
  }

  const data = JSON.parse(readFileSync(dataPath, 'utf-8'));
  const { month, imageText } = data;
  const template = MONTHLY_TEMPLATES[month] || MONTHLY_TEMPLATES[1];

  // Format date
  const now = new Date();
  const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`;

  // Output directory
  const outDir = '/mnt/c/Users/stsrj/Desktop/Instagram投稿';
  if (!existsSync(outDir)) {
    mkdirSync(outDir, { recursive: true });
  }

  const timestamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
  const outPath = join(outDir, `sato-math-post-${timestamp}.png`);

  // Launch Puppeteer
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 1 });

  // Load template HTML
  const templatePath = join(__dirname, 'template.html');
  await page.goto(`file://${templatePath}`, { waitUntil: 'load' });

  // Load eyecatch SVG if available
  const eyecatchPath = join(__dirname, 'eyecatch.svg');
  let eyecatchSvg = '';
  if (existsSync(eyecatchPath)) {
    eyecatchSvg = readFileSync(eyecatchPath, 'utf-8');
  }

  // Inject data into the template
  await page.evaluate((params) => {
    const { template, dateStr, imageText, eyecatchSvg } = params;

    // Decorative circles
    document.getElementById('deco-top').style.backgroundColor = template.accentBg;
    document.getElementById('deco-bottom').style.backgroundColor = template.accentBg;

    // Header
    document.getElementById('month-label').textContent = `${template.monthEn} Issue`;

    // Date and icon
    document.getElementById('icon').textContent = template.icon;
    document.getElementById('date').textContent = dateStr;

    // Headline and subhead
    document.getElementById('headline').textContent = imageText.headline;
    document.getElementById('subhead').textContent = imageText.subhead;
    document.getElementById('subhead-highlight').style.backgroundColor = template.highlightBg;

    // Body
    document.getElementById('body').textContent = imageText.body;

    // Accent bar
    document.getElementById('accent-bar').style.backgroundColor = template.accentColor;

    // Eyecatch SVG
    if (eyecatchSvg) {
      document.getElementById('eyecatch').innerHTML = eyecatchSvg;
    }
  }, { template, dateStr, imageText, eyecatchSvg });

  // Take screenshot
  await page.screenshot({
    path: outPath,
    type: 'png',
    clip: { x: 0, y: 0, width: 1080, height: 1080 },
  });

  await browser.close();

  console.log(`Image saved: ${outPath}`);
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
