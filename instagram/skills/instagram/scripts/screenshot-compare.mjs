import puppeteer from 'puppeteer';

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  // 1. Screenshot the original React app
  const page1 = await browser.newPage();
  await page1.setViewport({ width: 500, height: 900 });
  await page1.goto('http://localhost:5201', { waitUntil: 'networkidle0', timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  // Type some input and generate (or just capture the empty state to see layout)
  // Actually let's just inject post data via localStorage and reload
  await page1.evaluate(() => {
    // We just need to see the image template portion
    // Let's manually create the post state by calling the component
  });

  await page1.screenshot({
    path: '/mnt/c/Users/stsrj/Desktop/Instagram投稿/original-app-screenshot.png',
    fullPage: true,
  });
  console.log('Original app screenshot saved');

  // 2. Screenshot our preview.html
  const page2 = await browser.newPage();
  await page2.setViewport({ width: 800, height: 900 });
  await page2.goto('file:///mnt/c/Users/stsrj/Desktop/Instagram投稿/preview.html', { waitUntil: 'load' });
  await new Promise(r => setTimeout(r, 1000));
  await page2.screenshot({
    path: '/mnt/c/Users/stsrj/Desktop/Instagram投稿/our-preview-screenshot.png',
    fullPage: true,
  });
  console.log('Our preview screenshot saved');

  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
