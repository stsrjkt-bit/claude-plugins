#!/usr/bin/env node
// extract-figures.mjs
// atama+ COACH のモーダルから問題図形の base64 画像を抽出して PNG 保存する
//
// Usage:
//   node extract-figures.mjs --prefix kaitentai_enshu --outdir /tmp/hoshu_material
//
// 前提:
//   - Chrome が --remote-debugging-port=9222 で起動済み
//   - atama+ COACH のページが開いている
//   - モーダルが開いている状態（ion-modal.show-modal が存在する）
//   - ws モジュールが /tmp/node_modules/ にインストール済み

import { WebSocket } from '/tmp/node_modules/ws/wrapper.mjs';
import http from 'http';
import fs from 'fs';
import { parseArgs } from 'util';

const { values: args } = parseArgs({
  options: {
    prefix: { type: 'string', default: 'figure' },
    outdir: { type: 'string', default: '/tmp/hoshu_material' },
  },
});

function getPages() {
  return new Promise((resolve, reject) => {
    http.get('http://localhost:9222/json', (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });
}

function connectWS(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    ws.on('open', () => resolve(ws));
    ws.on('error', reject);
  });
}

let msgId = 1;
function cdp(ws, method, params = {}) {
  const id = msgId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`CDP timeout: ${method}`)), 15000);
    const handler = (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.id === id) {
        clearTimeout(timer);
        ws.removeListener('message', handler);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };
    ws.on('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evalJS(ws, expression) {
  const result = await cdp(ws, 'Runtime.evaluate', {
    expression,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'JS eval error');
  }
  return result.result.value;
}

async function main() {
  const { prefix, outdir } = args;
  fs.mkdirSync(outdir, { recursive: true });

  // Chrome に接続
  const pages = await getPages();
  const coachPage = pages.find((p) => p.url.includes('coach.atama.plus'));
  if (!coachPage) {
    console.error('ERROR: atama+ COACH のページが見つかりません');
    process.exit(1);
  }

  const ws = await connectWS(coachPage.webSocketDebuggerUrl);

  // モーダル内の base64 画像を全て抽出
  const raw = await evalJS(
    ws,
    `(() => {
      const modal = document.querySelector('ion-modal.show-modal');
      if (!modal) return JSON.stringify({ error: 'no-modal' });
      const imgs = modal.querySelectorAll('img');
      const results = [];
      imgs.forEach(img => {
        if (img.src.startsWith('data:image')) {
          results.push({
            w: img.naturalWidth,
            h: img.naturalHeight,
            data: img.src.replace(/^data:image\\/\\w+;base64,/, '')
          });
        }
      });
      return JSON.stringify({ count: results.length, figures: results });
    })()`,
  );

  const parsed = JSON.parse(raw);

  if (parsed.error) {
    console.error('ERROR: ' + parsed.error);
    ws.close();
    process.exit(1);
  }

  console.log(`Found ${parsed.count} figures in modal`);

  const saved = [];
  for (let i = 0; i < parsed.figures.length; i++) {
    const fig = parsed.figures[i];
    const buf = Buffer.from(fig.data, 'base64');
    const filename = `${prefix}_img${i}.png`;
    const filepath = `${outdir}/${filename}`;
    fs.writeFileSync(filepath, buf);
    saved.push({ filename, width: fig.w, height: fig.h, bytes: buf.length });
    console.log(`Saved ${filepath} (${fig.w}x${fig.h}, ${buf.length} bytes)`);
  }

  // JSON サマリーも出力
  const summary = { prefix, outdir, figures: saved };
  const summaryPath = `${outdir}/${prefix}_summary.json`;
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));
  console.log(`Summary: ${summaryPath}`);

  ws.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
