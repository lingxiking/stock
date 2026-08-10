import re

with open('index.html', 'r') as f:
    content = f.read()

# Fix: D类 scoring - use real-time data for today's limit-up detection
# This ensures stocks at limit-up today are detected even if K-line data failed

old_scoreD = """function scoreActiveLianban(stock, kline, indexChangePct) {
  const closes = kline.map(k=>k.close);
  const volumes = kline.map(k=>k.volume);
  const highs = kline.map(k=>k.high);
  const lows = kline.map(k=>k.low);
  const n = closes.length;
  const code = stock.code;
  const limit = getLimitPct(code);

  if (n < 20) return { score: 0, category: 'D' };

  const count = countCurrentConsecutiveLimitUps(closes, limit);
  if (count < 1) return { score: 0, category: 'D' };"""

new_scoreD = """function scoreActiveLianban(stock, kline, indexChangePct) {
  const closes = kline.map(k=>k.close);
  const volumes = kline.map(k=>k.volume);
  const highs = kline.map(k=>k.high);
  const lows = kline.map(k=>k.low);
  const n = closes.length;
  const code = stock.code;
  const limit = getLimitPct(code);

  // Use real-time change_pct to detect today's limit-up (more reliable than K-line)
  const stockChg = stock.change_pct;
  const todayLimitUp = stockChg >= limit * 0.98;

  // If no K-line data but today is limit-up, use simplified scoring
  if (n < 20) {
    if (!todayLimitUp) return { score: 0, category: 'D' };
    // Simplified: today is limit-up, score based on real-time data only
    const idxChg = indexChangePct || 0;
    const alpha = stockChg - idxChg;
    const turnover = stock.turnover_rate || 0;
    let total = 5; // base score for today's limit-up
    if (alpha > 5) total += 10;
    if (turnover >= 2 && turnover <= 8) total += 5;
    if (stockChg >= limit * 0.99) total += 5; // strong seal
    if (total >= 20) return { score: total, category: 'D', limit_up_days: 1, hist_max_consecutive_lu: 0 };
    return { score: 0, category: 'D' };
  }

  const klineCount = countCurrentConsecutiveLimitUps(closes, limit);
  // Combine K-line count with real-time: if today is limit-up per real-time but not in K-line, add 1
  const count = todayLimitUp ? Math.max(klineCount, 1) : klineCount;
  if (count < 1) return { score: 0, category: 'D' };"""

content = content.replace(old_scoreD, new_scoreD)

# Also fix the variable reference - stockChg was defined later, now it's used earlier
# Remove the duplicate stockChg definition
content = content.replace(
    """  const stockChg = stock.change_pct;
  const idxChg = indexChangePct || 0;
  const alpha = stockChg - idxChg;
  const turnover = stock.turnover_rate || 0;
  const vr = calcVolRatio(kline);""",
    """  const idxChg = indexChangePct || 0;
  const alpha = stockChg - idxChg;
  const turnover = stock.turnover_rate || 0;
  const vr = calcVolRatio(kline);""",
    1  # only replace first occurrence (in scoreActiveLianban)
)

# Update version
content = content.replace('v7.9d', 'v7.9e')

with open('index.html', 'w') as f:
    f.write(content)

print("Done - v7.9e applied")
