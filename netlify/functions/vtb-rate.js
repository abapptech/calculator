// netlify/functions/vtb-rate.js
// Получает курс CNY/RUB из API ВТБ, с fallback через CORS-прокси.

const VTB_URL = 'https://www.vtb.ru/api/currencyrates/table/optimized?category=3&type=1';

const BROWSER_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
  'Referer': 'https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/yuan/',
};

// Рекурсивно ищем узлы, описывающие пару CNY/RUB
function extractCny(data) {
  const found = [];
  (function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    const c1 = node.currency1 && node.currency1.code;
    const c2 = node.currency2 && node.currency2.code;
    if (c1 === 'CNY' && c2 === 'RUB' && node.offer != null) {
      found.push(node);
    }
    Object.values(node).forEach(walk);
  })(data);
  return found;
}

// Из списка найденных тарифов выбираем основной (наименьший диапазон сумм, если он определён)
function pickPrimary(tiers) {
  if (!tiers.length) return null;
  const withRange = tiers.filter(t => {
    const upper = t.amountTo ?? t.upperLimit ?? t.limitTo ?? t.maxAmount ?? t.max;
    return upper != null;
  });
  if (withRange.length) {
    withRange.sort((a, b) => {
      const ua = a.amountTo ?? a.upperLimit ?? a.limitTo ?? a.maxAmount ?? a.max ?? Infinity;
      const ub = b.amountTo ?? b.upperLimit ?? b.limitTo ?? b.maxAmount ?? b.max ?? Infinity;
      return ua - ub;
    });
    return withRange[0];
  }
  return tiers[0];
}

function buildResult(data, via) {
  const tiers = extractCny(data);
  if (!tiers.length) return null;
  const p = pickPrimary(tiers);
  if (!p || p.offer == null || p.bid == null) return null;
  const scale = p.scale || 1;
  return {
    cny_sell: p.offer / scale,
    cny_buy: p.bid / scale,
    tiers,
    source: 'vtb',
    via,
    ts: Date.now(),
  };
}

async function fetchWithTimeout(url, opts = {}, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...opts, signal: controller.signal });
    return r;
  } finally {
    clearTimeout(timer);
  }
}

exports.handler = async function () {
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
  };

  const attempts = [
    // 1. Прямой запрос
    {
      via: 'direct',
      run: () => fetchWithTimeout(VTB_URL, { headers: BROWSER_HEADERS }, 12000),
      parse: async (r) => r.json(),
    },
    // 2. corsproxy.io
    {
      via: 'proxy1',
      run: () => fetchWithTimeout('https://corsproxy.io/?url=' + encodeURIComponent(VTB_URL), {}, 15000),
      parse: async (r) => r.json(),
    },
    // 3. allorigins
    {
      via: 'proxy2',
      run: () => fetchWithTimeout('https://api.allorigins.win/get?url=' + encodeURIComponent(VTB_URL), {}, 18000),
      parse: async (r) => {
        const wrapper = await r.json();
        return JSON.parse(wrapper.contents);
      },
    },
    // 4. thingproxy
    {
      via: 'proxy3',
      run: () => fetchWithTimeout('https://thingproxy.freeboard.io/fetch/' + VTB_URL, {}, 15000),
      parse: async (r) => r.json(),
    },
  ];

  const errors = [];

  for (const attempt of attempts) {
    try {
      const r = await attempt.run();
      if (!r.ok) {
        errors.push(`${attempt.via}: HTTP ${r.status}`);
        continue;
      }
      const data = await attempt.parse(r);
      const result = buildResult(data, attempt.via);
      if (result) {
        return { statusCode: 200, headers, body: JSON.stringify(result) };
      }
      errors.push(`${attempt.via}: CNY не найден в ответе`);
    } catch (e) {
      errors.push(`${attempt.via}: ${e.message || e}`);
    }
  }

  return {
    statusCode: 502,
    headers,
    body: JSON.stringify({ error: 'Все источники недоступны', details: errors, ts: Date.now() }),
  };
};
