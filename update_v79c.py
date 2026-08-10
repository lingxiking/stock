with open('/tmp/stock/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace fetchKline - use Sina JSONP (script tag) as primary, Tencent fetch as fallback
old_fk = '''async function fetchKline(code, market, days=60) {
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

new_fk = '''async function fetchKline(code, market, days=60) {
  const fetchDays = Math.max(days + 20, 80);
  const prefix = market === 1 ? 'sh' : 'sz';
  const symbol = `${prefix}${code}`;

  // Primary: Sina JSONP via script tag (CORS-proof)
  try {
    const cbVar = `_sk_${symbol}_${Date.now()}`;
    const klines = await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timer = setTimeout(() => { cleanup(); reject('sina timeout'); }, 4000);
      function cleanup() {
        clearTimeout(timer);
        try { delete window[cbVar]; } catch(e) {}
        if (script.parentNode) script.parentNode.removeChild(script);
      }
      window[cbVar] = function(resp) {
        cleanup();
        if (Array.isArray(resp) && resp.length > 0 && resp[0].day) {
          resolve(resp.map(d => ({
            time: d.day, open: +d.open, close: +d.close,
            high: +d.high, low: +d.low, volume: +d.volume,
          })));
        } else { reject('sina empty'); }
      };
      script.onerror = () => { cleanup(); reject('sina error'); };
      script.src = `https://quotes.sina.cn/cn/api/jsonp.php/${cbVar}(/CN_MarketDataService.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${fetchDays}&_=${Date.now()}`;
      document.head.appendChild(script);
    });
    if (klines.length >= 10) return klines.slice(-days);
  } catch(e) { /* Sina failed, try Tencent */ }

  // Fallback: Tencent fetch
  try {
    const resp = await fetch(`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,,,${fetchDays},qfq`, { cache: 'no-store' });
    if (resp.ok) {
      const data = await resp.json();
      const stockData = data?.data?.[symbol];
      if (stockData) {
        const klines = stockData.qfqday || stockData.day || [];
        if (klines.length > 0) return klines.slice(-days).map(line => ({
          time: line[0], open: +line[1], close: +line[2],
          high: +line[3], low: +line[4], volume: +line[5],
        }));
      }
    }
  } catch(e) { /* fail */ }

  return [];
}'''

if old_fk in content:
    content = content.replace(old_fk, new_fk)
    print("  ✓ fetchKline: Sina JSONP primary + Tencent fallback")
else:
    print("  ✗ fetchKline pattern not found")

# Update fetchKlinesBatch concurrency (Sina via script tag is slower, reduce concurrency)
content = content.replace(
    'const CONC = 12;\n  const IV = 80;',
    'const CONC = 6;\n  const IV = 100;'
)

with open('/tmp/stock/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("v7.9c applied!")
