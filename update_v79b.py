with open('/tmp/stock/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

# 1. Replace fetchKline function (simplified - single URL, no retry, no Sina)
old_fk = '''async function fetchKline(code, market, days=60) {
  const fetchDays = Math.max(days + 20, 80);
  const prefix = market === 1 ? 'sh' : 'sz';
  const symbol = `${prefix}${code}`;

  // Source 1: Tencent kline API with fallback URLs
  for (let retry = 0; retry < 2; retry++) {
    const urls = [
      `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,,,${fetchDays},qfq`,
      `https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=${symbol},day,,${fetchDays}`
    ];
    for (const url of urls) {
      try {
        const resp = await fetch(url, { cache: 'no-cache' });
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.data) {
            const stockData = data.data[symbol];
            if (stockData) {
              const klines = stockData.qfqday || stockData.day || [];
              if (klines.length > 0) {
                return klines.slice(-days).map(line => ({
                  time: line[0], open: +line[1], close: +line[2],
                  high: +line[3], low: +line[4], volume: +line[5],
                }));
              }
            }
          }
        }
      } catch(e) { /* try next */ }
    }
    if (retry === 0) await new Promise(r => setTimeout(r, 500));
  }

  // Source 2: Sina JSONP fallback
  try {
    const cbVar = `_sinaKline_${symbol}`;
    const result = await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timeout = setTimeout(() => { cleanup(); reject(new Error('Sina timeout')); }, 8000);
      function cleanup() { clearTimeout(timeout); try { delete window[cbVar]; } catch(e) {} if (script.parentNode) script.parentNode.removeChild(script); }
      window[cbVar] = function(data) {
        cleanup();
        if (data && Array.isArray(data) && data.length > 0 && data[0].day) {
          resolve(data.slice(-days).map(d => ({ time: d.day, open: +d.open, close: +d.close, high: +d.high, low: +d.low, volume: +d.volume })));
        } else { reject(new Error('Sina empty')); }
      };
      script.onerror = () => { cleanup(); reject(new Error('Sina error')); };
      script.src = `https://quotes.sina.cn/cn/api/jsonp.php/${cbVar}(/CN_MarketDataService.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${fetchDays}&_=${Date.now()}`;
      document.head.appendChild(script);
    });
    return result;
  } catch(e) { /* Sina also failed */ }

  return [];
}'''

new_fk = '''async function fetchKline(code, market, days=60) {
  const fetchDays = Math.max(days + 20, 80);
  const prefix = market === 1 ? 'sh' : 'sz';
  const symbol = `${prefix}${code}`;
  try {
    const resp = await fetch(`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,,,${fetchDays},qfq`, { cache: 'no-store' });
    if (resp.ok) {
      const data = await resp.json();
      const stockData = data?.data?.[symbol];
      if (stockData) {
        const klines = stockData.qfqday || stockData.day || [];
        if (klines.length > 0) {
          return klines.slice(-days).map(line => ({
            time: line[0], open: +line[1], close: +line[2],
            high: +line[3], low: +line[4], volume: +line[5],
          }));
        }
      }
    }
  } catch(e) { /* fail */ }
  return [];
}'''

if old_fk in content:
    content = content.replace(old_fk, new_fk)
    print("  ✓ fetchKline simplified")
else:
    print("  ✗ fetchKline pattern not found, trying line-by-line...")
    # Find function boundaries
    start = content.find('async function fetchKline(code, market, days=60) {')
    end = content.find('async function fetchKlinesBatch')
    if start != -1 and end != -1:
        # Find the line before fetchKlinesBatch
        before_batch = content.rfind('\n', start, end)
        content = content[:start] + new_fk + '\n' + content[end:]
        print("  ✓ fetchKline replaced (line-by-line)")
    else:
        print(f"  ✗ Could not find boundaries: start={start}, end={end}")

# 2. Replace fetchKlinesBatch (add progress, increase concurrency)
old_fb = '''async function fetchKlinesBatch(stocks, days=60) {
  const results = {};
  // Pre-filter for K-line scoring
  const active = stocks.filter(s => s.change_pct >= -3 && s.amount >= 100); // amount in 万元, threshold=100万
  console.log(`K-line pre-filter: ${stocks.length} -> ${active.length}`);

  const CONC = 8;
  const IV = 150;
  for (let i = 0; i < active.length; i += CONC) {
    const batch = active.slice(i, i + CONC);
    const promises = batch.map(async s => {
      const kline = await fetchKline(s.code, s.market, days);
      if (kline.length >= 10) results[s.code] = kline;
    });
    await Promise.all(promises);
    if (i + CONC < active.length) await new Promise(r => setTimeout(r, IV));
  }
  console.log(`K-line done: ${Object.keys(results).length}`);
  return results;
}'''

new_fb = '''async function fetchKlinesBatch(stocks, days=60) {
  const results = {};
  const active = stocks.filter(s => s.change_pct >= -3 && s.amount >= 100);
  console.log(`K-line pre-filter: ${stocks.length} -> ${active.length}`);

  const CONC = 12;
  const IV = 80;
  let okCount = 0;
  for (let i = 0; i < active.length; i += CONC) {
    const batch = active.slice(i, i + CONC);
    await Promise.all(batch.map(async s => {
      const kline = await fetchKline(s.code, s.market, days);
      if (kline.length >= 10) { results[s.code] = kline; okCount++; }
    }));
    const pt = document.getElementById('progressText');
    if (pt) pt.textContent = `拉取K线 ${Math.min(i+CONC,active.length)}/${active.length} 成功${okCount}只`;
    if (i + CONC < active.length) await new Promise(r => setTimeout(r, IV));
  }
  console.log(`K-line done: ${okCount}/${active.length}`);
  return results;
}'''

if old_fb in content:
    content = content.replace(old_fb, new_fb)
    print("  ✓ fetchKlinesBatch updated")
else:
    print("  ✗ fetchKlinesBatch exact match failed, doing manual replace...")
    # Find and replace key parts
    content = content.replace('const CONC = 8;\n  const IV = 150;', 'const CONC = 12;\n  const IV = 80;\n  let okCount = 0;')
    content = content.replace(
        'if (kline.length >= 10) results[s.code] = kline;\n    });\n    await Promise.all(promises);',
        'if (kline.length >= 10) { results[s.code] = kline; okCount++; }\n    }));\n    await Promise.all(batch.map(async s => {})); // no-op for compat'
    )
    print("  ⚠ Partial replacement done - manual review needed")

# 3. Replace fetchMarketIndex with Tencent API
old_mi_start = '// ── Market Index ──\nasync function fetchMarketIndex() {'
old_mi_end = "return { price: 0, change_pct: 0 };\n}"

mi_start = content.find(old_mi_start)
mi_end = content.find(old_mi_end, mi_start) if mi_start != -1 else -1

if mi_start != -1 and mi_end != -1:
    mi_end += len(old_mi_end)
    new_mi = '''// ── Market Index ──
async function fetchMarketIndex() {
  try {
    const resp = await fetch('https://qt.gtimg.cn/q=sh000001', { cache: 'no-store' });
    const buf = await resp.arrayBuffer();
    let text;
    try { text = new TextDecoder('gbk').decode(buf); } catch(e) { text = new TextDecoder('utf-8').decode(buf); }
    const m = text.match(/v_sh000001="([^"]*)"/);
    if (m) {
      const f = m[1].split('~');
      if (f.length > 32) return { price: parseFloat(f[3]) || 0, change_pct: parseFloat(f[32]) || 0 };
    }
  } catch(e) { console.warn('Index error:', e); }
  return { price: 0, change_pct: 0 };
}
'''
    content = content[:mi_start] + new_mi + content[mi_end:]
    print("  ✓ fetchMarketIndex switched to qt.gtimg.cn")
else:
    print(f"  ✗ fetchMarketIndex not found: start={mi_start}, end={mi_end}")

with open('/tmp/stock/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone! Ready to commit.")
