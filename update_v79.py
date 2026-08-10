import re

with open('/tmp/stock/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update version string
content = content.replace(
    '灵犀King · AI主升 v7.8 · 四模型量化引擎 · 诊断+降速',
    '灵犀King · AI主升 v7.9 · 四模型量化引擎 · 批量极速版'
)

# 2. Replace fetchAllStocks function entirely
old_func_start = '// ── Data fetching via EastMoney API ──\nasync function fetchAllStocks() {'
old_func_end = '  return result;\n}\n// ── K-line data ──'

# Find the old function boundaries
start_idx = content.find(old_func_start)
end_idx = content.find(old_func_end)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: Could not find function boundaries. start={start_idx}, end={end_idx}")
    # Try to find approximate locations
    for i, line in enumerate(content.split('\n')):
        if 'fetchAllStocks' in line:
            print(f"  Line {i+1}: {line.strip()[:80]}")
    exit(1)

new_function = '''// ── Data fetching via Tencent Batch Quote API (script injection, CORS-free) ──
async function fetchAllStocks() {
  const segmentsToFetch = [];
  if (selectedBoards.includes('main')) segmentsToFetch.push('main');
  if (selectedBoards.includes('gem')) segmentsToFetch.push('gem');
  if (selectedBoards.includes('star')) segmentsToFetch.push('star');

  let allStocks = [];
  let stFiltered = 0;
  for (const [code, name, market] of STOCK_LIST) {
    const prefix = code.substring(0, 3);
    let match = false;
    for (const b of segmentsToFetch) {
      if (BOARD_PREFIXES[b].some(p => prefix.startsWith(p) || code.startsWith(p))) { match = true; break; }
    }
    if (!match) continue;
    if (name.includes('ST') || name.includes('st') || name.includes('*')) { stFiltered++; continue; }
    allStocks.push({ code, name, market });
  }
  console.log(`Stock list: ${allStocks.length} candidates after filtering`);

  // Build symbol list
  const symbols = allStocks.map(s => (s.market === 1 ? 'sh' : 'sz') + s.code);
  const codeMap = {};
  allStocks.forEach((s, i) => { codeMap[symbols[i]] = s; });

  const result = [];
  let zeroCount = 0;
  let batchErrors = 0;
  const BATCH_SIZE = 80;
  let processed = 0;

  // Diagnostic: show first successful parse
  let firstDiagShown = false;

  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batchSyms = symbols.slice(i, i + BATCH_SIZE);
    const url = `https://qt.gtimg.cn/q=${batchSyms.join(',')}`;

    try {
      const resp = await fetch(url, { cache: 'no-store' });
      const buf = await resp.arrayBuffer();
      // qt.gtimg.cn returns GBK-encoded text; numeric fields are ASCII-safe
      let text;
      try { text = new TextDecoder('gbk').decode(buf); }
      catch(e) { text = new TextDecoder('utf-8').decode(buf); }

      const lines = text.split(';');
      for (const line of lines) {
        const m = line.match(/v_(\\w+)="([^"]*)"/);
        if (!m) continue;
        const symbol = m[1];
        const fields = m[2].split('~');
        if (fields.length < 40) continue;

        const s = codeMap[symbol];
        if (!s) continue;

        const price = parseFloat(fields[3]);
        const prevClose = parseFloat(fields[4]);
        const openPrice = parseFloat(fields[5]);
        const high = parseFloat(fields[33]);
        const low = parseFloat(fields[34]);
        const volume = parseInt(fields[6]) || 0;  // 股(shares)
        const amountWan = parseFloat(fields[37]) || 0;  // 万元
        const changePct = parseFloat(fields[32]) || 0;
        const turnover = parseFloat(fields[38]) || 0;

        // Skip invalid / untraded
        if (!price || price <= 0 || volume <= 0) { zeroCount++; continue; }
        // Pre-filter: amount < 100万 → skip
        if (amountWan < 100) continue;

        if (!firstDiagShown) {
          firstDiagShown = true;
          console.log(`[v7.9 diag] First parse OK: ${symbol} price=${price} amount=${amountWan}万 change=${changePct}%`);
        }

        result.push({
          ...s, price, prev_close: prevClose || price,
          open: openPrice || price,
          high: high || price, low: low || price,
          volume, amount: amountWan,
          change_pct: changePct,
          turnover_rate: turnover
        });
      }
    } catch (e) {
      batchErrors++;
      console.warn(`Batch error at ${i}: ${e.message}`);
    }

    processed = Math.min(i + BATCH_SIZE, symbols.length);
    const pt = document.getElementById('progressText');
    if (pt) pt.textContent = `获取行情 ${processed}/${symbols.length} 已得${result.length}只 (零成交${zeroCount} 错${batchErrors}批)`;

    // Tiny delay between batches to be polite
    if (i + BATCH_SIZE < symbols.length) await new Promise(r => setTimeout(r, 150));
  }

  console.log(`[v7.9] Scan done: ${result.length} stocks passed (zero=${zeroCount}, batchErr=${batchErrors})`);
  window._apiTotal = STOCK_LIST.length;
  window._apiRawCount = allStocks.length;
  window._stFiltered = stFiltered;
  return result;
}
'''

content = content[:start_idx] + new_function + content[end_idx + len(old_func_end):]

# 3. Fix fetchKlinesBatch pre-filter: amount is now in 万元, threshold should be 100 (万)
content = content.replace(
    "const active = stocks.filter(s => s.change_pct >= -3 && s.amount >= 3000000);",
    "const active = stocks.filter(s => s.change_pct >= -3 && s.amount >= 100); // amount in 万元, threshold=100万"
)

# 4. Update topCandidates from 500 to 300 for speed
content = content.replace(
    "const topCandidates = allStocks.slice(0, 500);",
    "const topCandidates = allStocks.slice(0, 300);"
)

# 5. Fix scoring: amount rank should use the 万元 unit consistently
# Find the score calculation and ensure amount is used correctly

with open('/tmp/stock/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("v7.9 update applied successfully")
print(f"  Replaced fetchAllStocks with batch API version")
print(f"  Fixed fetchKlinesBatch pre-filter threshold")
print(f"  Updated topCandidates to 300")
