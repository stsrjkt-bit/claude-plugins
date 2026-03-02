import puppeteer from 'puppeteer';
import { existsSync, mkdirSync } from 'fs';
import { resolve } from 'path';

const OUTPUT_DIR = '/mnt/c/Users/stsrj/Desktop/補習プリント';

async function generatePdf(htmlPath, outputPath) {
  const absHtml = resolve(htmlPath);
  if (!existsSync(absHtml)) {
    console.error(`Error: HTML file not found: ${absHtml}`);
    process.exit(1);
  }

  // 出力ディレクトリ作成
  mkdirSync(OUTPUT_DIR, { recursive: true });

  const absOutput = outputPath.startsWith('/')
    ? outputPath
    : resolve(OUTPUT_DIR, outputPath);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();

  // HTMLを開く
  await page.goto(`file://${absHtml}`, { waitUntil: 'networkidle0', timeout: 30000 });

  // MathJax v3のレンダリング完了を待機
  await page.evaluate(() => {
    return new Promise((resolve) => {
      if (typeof MathJax !== 'undefined' && MathJax.startup) {
        MathJax.startup.promise.then(() => resolve());
      } else {
        // MathJaxがない場合はそのまま進む
        resolve();
      }
    });
  });

  // 少し待機（フォントレンダリング安定化）
  await new Promise((r) => setTimeout(r, 500));

  // PDF生成
  await page.pdf({
    path: absOutput,
    format: 'A4',
    margin: { top: '20mm', right: '18mm', bottom: '20mm', left: '18mm' },
    printBackground: true,
    displayHeaderFooter: false,
  });

  await browser.close();
  console.log(`PDF saved: ${absOutput}`);
}

// CLI: node generate-pdf.mjs <input.html> [output.pdf]
const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node generate-pdf.mjs <input.html> [output.pdf]');
  console.error('  output.pdf defaults to 補習プリント folder on Desktop');
  process.exit(1);
}

const inputHtml = args[0];
const outputPdf = args[1] || inputHtml.replace(/\.html$/, '.pdf').split('/').pop();

generatePdf(inputHtml, outputPdf).catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
