(function () {
  'use strict';

  const D = window.DASHBOARD_DATA;
  const LS = { simpleView: 'qmst-simple-view', sectionsCollapsed: 'qmst-section-collapsed' };

  if (!D) {
    document.body.innerHTML = '<p style="padding:48px;color:#ff6b6b">Run python3 scripts/build_analysis_dashboard.py</p>';
    return;
  }

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const fmt = (n) => {
    if (n == null || isNaN(n)) return '—';
    const v = Math.round(Number(n));
    if (Math.abs(v) >= 100000) return '₹' + (v / 100000).toFixed(2) + 'L';
    if (Math.abs(v) >= 1000) return '₹' + (v / 1000).toFixed(1) + 'k';
    return '₹' + v.toLocaleString('en-IN');
  };

  const SEV = {
    vmq: 'sell', sell_breakdown: 'sell', sell: 'sell', lvmrot: 'sell', exit: 'sell',
    swap: 'buy', buynew: 'buy', increase: 'buy', rsipullback: 'buy',
    watch: 'warn', radar: 'warn', hold: 'warn', hold_note: 'warn',
    intro: 'info', final_numbers: 'info', dual: 'info', path2: 'info',
  };

  /** Meta / duplicate blocks — from payload dashboardPolicy (single source of truth). */
  const POLICY = D.dashboardPolicy || {};
  const SKIP_SECTIONS = new Set(POLICY.skipSections || [
    'intro', 'vmq', 'path2', 'dual', 'hold_note', 'hold', 'sell_breakdown',
  ]);
  const MONITOR_SECTIONS = new Set(POLICY.monitorSectionIds || ['radar', 'watch']);

  function sectionEmpty(sec) {
    if (sec.kind === 'footer') return false;
    if (sec.grouped) return !sec.grouped.some((g) => (g.stocks || []).length);
    return !(sec.items || []).length;
  }

  function visibleSections() {
    return (D.actionDocument || {}).sections.filter((s) => {
      if (SKIP_SECTIONS.has(s.id)) return false;
      if (sectionEmpty(s)) return false;
      return true;
    });
  }

  function countActions() {
    let sellN = 0;
    let buyN = 0;
    visibleSections().forEach((sec) => {
      const id = sec.id || '';
      const n = sectionItems(sec).length;
      if (/sell|exit|lvmrot/.test(id)) sellN += n;
      else if (id === 'swap') {
        sellN += n;
        buyN += n;
      } else if (/buynew|increase/.test(id)) buyN += n;
    });
    return { sellN, buyN };
  }

  function holdingPnlPct(r) {
    if (r.pnlPctAlloc != null && r.pnlPctAlloc !== '') return Number(r.pnlPctAlloc);
    if (r.pnlPct != null && r.pnlPct !== '') return Number(r.pnlPct);
    return null;
  }

  function formatPnlSpan(pnlVal) {
    if (pnlVal == null || pnlVal === '' || Number.isNaN(Number(pnlVal))) return '—';
    const v = Number(pnlVal);
    const cls = v >= 0 ? 'up' : 'down';
    const sign = v > 0 ? '+' : '';
    return '<span class="' + cls + '">' + sign + v.toFixed(1) + '%</span>';
  }

  function stockLabel(item) {
    const sym = item.stock || '';
    if (item.targetSymbol) return sym + ' → ' + item.targetSymbol;
    return sym;
  }

  function showCopyToast(sym) {
    let t = document.querySelector('.copy-toast');
    if (!t) {
      t = document.createElement('div');
      t.className = 'copy-toast';
      t.setAttribute('role', 'status');
      t.setAttribute('aria-live', 'polite');
      document.body.appendChild(t);
    }
    t.textContent = sym + ' copied';
    t.classList.add('show');
    clearTimeout(showCopyToast._timer);
    showCopyToast._timer = setTimeout(() => t.classList.remove('show'), 1600);
  }

  function copySymbol(sym, btn) {
    const text = String(sym || '').trim();
    if (!text) return;
    const done = () => {
      showCopyToast(text);
      if (btn) {
        btn.classList.add('copied');
        setTimeout(() => btn.classList.remove('copied'), 900);
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => {
        fallbackCopy(text);
        done();
      });
    } else {
      fallbackCopy(text);
      done();
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (_) { /* ignore */ }
    document.body.removeChild(ta);
  }

  function tvUrl(sym) {
    return 'https://in.tradingview.com/chart/4dVOBVwE/?symbol=NSE%3A' + encodeURIComponent(sym);
  }
  function screenerUrl(sym) {
    return 'https://www.screener.in/company/' + encodeURIComponent(sym) + '/consolidated/';
  }

  function stockCellHTML(item) {
    const sym = item.stock || '';
    const co = item.company || '';
    let h = '<div class="sym-cell">';
    if (item.targetSymbol) {
      h += '<span class="sym-row">';
      h += '<a href="' + tvUrl(sym) + '" target="_blank" rel="noopener" class="sym-name" title="Open ' + esc(sym) + ' on TradingView">' + esc(sym) + '</a>';
      h += '<span class="sym-arrow">→</span>';
      h += '<a href="' + tvUrl(item.targetSymbol) + '" target="_blank" rel="noopener" class="sym-name sym-target" title="Open ' + esc(item.targetSymbol) + ' on TradingView">' + esc(item.targetSymbol) + '</a>';
      h += '</span>';
    } else {
      h += '<a href="' + tvUrl(sym) + '" target="_blank" rel="noopener" class="sym-name" title="Open ' + esc(sym) + ' on TradingView">' + esc(sym) + '</a>';
    }
    if (co) h += '<a href="' + screenerUrl(sym) + '" target="_blank" rel="noopener" class="sym-co" title="Open ' + esc(co) + ' on Screener">' + esc(co) + '</a>';
    h += '</div>';
    return h;
  }

  function priceCellHTML(item) {
    const p = item.price;
    if (p == null || p === '' || Number(p) === 0) return '—';
    return '₹' + Number(p).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }

  function sectionNumLabel(sec) {
    const m = (sec.headline || '').match(/Priority\s+([\d]+(?:\.[\d]+)?)\s*:/i);
    if (m) return 'P' + m[1];
    if (sec.id === 'radar') return 'P4';
    if (sec.id === 'final_numbers') return '∑';
    return '—';
  }

  function gttStopInfo(item) {
    if (item.gttStop) {
      return { stop: Number(item.gttStop), pct: item.gttStopPct != null ? Number(item.gttStopPct) : 10 };
    }
    const ms = item.monitorScenarios;
    const m2 = ms && (ms.m2 || '');
    if (!m2) return null;
    const m = String(m2).match(/GTT stop ₹([\d,]+(?:\.\d+)?)/i);
    if (!m) return null;
    const stop = Number(m[1].replace(/,/g, ''));
    const pctM = String(m2).match(/\(-(\d+(?:\.\d+)?)%\)/);
    return { stop, pct: pctM ? Number(pctM[1]) : 10 };
  }

  function stopDisplayHTML(item) {
    const gtt = gttStopInfo(item);
    if (gtt && gtt.stop > 0) {
      let h = '<span class="stop-gtt">GTT ₹' + gtt.stop.toLocaleString('en-IN') + ' (-' + gtt.pct + '%)</span>';
      if (item.stopLoss && Math.abs(Number(item.stopLoss) - gtt.stop) > 0.01) {
        h += '<span class="stop-book">Book ₹' + Number(item.stopLoss).toLocaleString('en-IN') + '</span>';
      }
      return h;
    }
    if (item.stopLoss) {
      return '<span>₹' + Number(item.stopLoss).toLocaleString('en-IN') + '</span>';
    }
    return '—';
  }

  function riskMetaHTML(item) {
    const parts = [];
    const gtt = gttStopInfo(item);
    if (gtt && gtt.stop > 0) {
      parts.push('GTT ₹' + gtt.stop.toLocaleString('en-IN') + ' (-' + gtt.pct + '%)');
      if (item.stopLoss && Math.abs(Number(item.stopLoss) - gtt.stop) > 0.01) {
        parts.push('Book ₹' + Number(item.stopLoss).toLocaleString('en-IN'));
      }
    } else if (item.stopLoss) {
      parts.push('Stop ₹' + Number(item.stopLoss).toLocaleString('en-IN'));
    }
    if (item.bookPct != null && item.bookPct > 0 && item.bookPct < 100) {
      parts.push('Book ' + item.bookPct + '%');
    } else if (item.bookPct === 100) {
      parts.push('Exit 100%');
    }
    if (item.sleeve) parts.push(item.sleeve);
    if (item.stopTier && item.stopTier !== 'NONE') parts.push(item.stopTier);
    return parts.length ? parts.join(' · ') : '—';
  }

  function vmqSellNote(sec) {
    if (sec.id !== 'sell') return '';
    const items = sec.items || [];
    if (!items.length) return '';
    const vmqN = items.filter((i) => /^VMQ_/.test(String(i.sellWhy || ''))).length;
    if (vmqN === items.length) {
      return '<p class="sec-note vmq-note">All exits this week: VMQ loss stops (−8% / −5%) — execute per REASON.</p>';
    }
    if (vmqN > 0) {
      return '<p class="sec-note vmq-note">' + vmqN + ' of ' + items.length + ' exits: VMQ stops.</p>';
    }
    return '';
  }

  let simpleView = localStorage.getItem(LS.simpleView) !== 'false';
  if (simpleView) document.body.classList.add('simple-view');

  function actionClass(a) {
    const x = String(a || '').toUpperCase();
    if (/SELL|EXIT/.test(x)) return 'act-sell';
    if (/BUY|NEW|SWAP|INCREASE/.test(x)) return 'act-buy';
    return 'act-warn';
  }

  function actionLabel(a) {
    const x = String(a || '').toUpperCase();
    if (/SELL/.test(x) && !/CONSIDER/.test(x)) return 'Sell';
    if (/SWAP/.test(x)) return 'Swap';
    if (/CONSIDER|REDUCE|BOOK/.test(x)) return 'Review';
    if (/NEW|INCREASE/.test(x)) return 'Add';
    if (/BUY/.test(x) && !/NEW/.test(x)) return 'Buy';
    if (/WATCH|CONFIRM|SKIP/.test(x)) return 'Watch';
    if (/KEEP/.test(x)) return 'Keep';
    if (/HOLD/.test(x)) return 'Hold';
    return a || '—';
  }

  /** Terminal-style action order for holdings table. */
  function holdingActionRank(action) {
    const x = String(action || 'HOLD').toUpperCase();
    if (/\bSELL\b|\bEXIT\b/.test(x) && !/CONSIDER/.test(x)) return 0;
    if (/SWAP/.test(x)) return 1;
    if (/CONSIDER|REDUCE|BOOK|SCALE/.test(x)) return 2;
    if (/INCREASE|NEW POSITION|BREAKOUT|\bNEW\b|\bBUY\b/.test(x)) return 3;
    if (/WATCH|CONFIRM|SKIP/.test(x)) return 4;
    if (/KEEP|\bHOLD\b/.test(x)) return 5;
    return 6;
  }

  function holdingActionGroupLabel(rank) {
    return ({
      0: 'Exit — sell this week',
      1: 'Swap — rotate',
      2: 'Review — optional trim',
      3: 'Add — increase / new',
      4: 'Watch — no trade yet',
      5: 'Hold — no trade',
    })[rank] || 'Other';
  }

  function sortHoldings(rows) {
    return rows.slice().sort((a, b) => {
      const ra = holdingActionRank(a.action);
      const rb = holdingActionRank(b.action);
      if (ra !== rb) return ra - rb;
      return (Number(b.value) || 0) - (Number(a.value) || 0);
    });
  }

  function loadSectionCollapsedState() {
    try {
      return JSON.parse(localStorage.getItem(LS.sectionsCollapsed) || '{}');
    } catch (_e) {
      return {};
    }
  }

  function saveSectionCollapsedState(state) {
    localStorage.setItem(LS.sectionsCollapsed, JSON.stringify(state));
  }

  let sectionCollapsedState = loadSectionCollapsedState();

  function isSectionCollapsed(secId) {
    if (Object.prototype.hasOwnProperty.call(sectionCollapsedState, secId)) {
      return !!sectionCollapsedState[secId];
    }
    return MONITOR_SECTIONS.has(secId);
  }

  function sectionItems(sec) {
    if (sec.grouped) {
      const out = [];
      sec.grouped.forEach((g) => g.stocks.forEach((s) => out.push(s)));
      return out;
    }
    return sec.items || [];
  }

  function runSymbols(sec) {
    const syms = sectionItems(sec).map((i) => i.stock).filter(Boolean);
    return [...new Set(syms)];
  }

  const G = D.actionPlanGuide || {};

  function lookupTier(tier) {
    const t = (G.radarTiers || []).find((x) => x.tier === tier);
    return t ? t.meaning : '';
  }

  function decodeReasonPlain(reason) {
    const text = String(reason || '').trim();
    if (!text) return '';
    const upper = text.toUpperCase();
    for (const pat of (G.reasonPatterns || [])) {
      const p = String(pat.pattern || '').toUpperCase();
      if (p && upper.includes(p)) return pat.plain || '';
    }
    return '';
  }

  function lookupEntry(code) {
    const e = (G.entryScenarios || []).find((x) => x.code === code);
    return e ? e.meaning : '';
  }

  function codeChip(code, meaning, cls) {
    if (!code) return '';
    const m = meaning || '';
    return '<span class="code-chip' + (cls ? ' ' + cls : '') + '"' +
      (m ? ' title="' + esc(m) + '"' : '') + '><b>' + esc(code) + '</b>' +
      (m ? '<span class="chip-mean">' + esc(m) + '</span>' : '') + '</span>';
  }

  function whyCellHTML(item) {
    const plain = item.reasonPlain || decodeReasonPlain(item.reason) || '';
    const raw = item.reason || '';
    let h = '';
    if (item.sellWhy && item.sellWhy !== 'NOT_SELL') {
      h += codeChip(item.sellWhy, item.sellWhyPlain || item.sellWhy, 'sellwhy');
    }
    h += '<div class="plain">' + esc(plain || raw || '—') + '</div>';
    if (raw) h += '<div class="raw">' + esc(raw) + '</div>';
    return h;
  }

  function parseScenarios(ep, prefix) {
    if (!ep) return null;
    if (prefix === 'S' && (ep.s1 || ep.s2 || ep.s3)) {
      return { s1: ep.s1 || '', s2: ep.s2 || '', s3: ep.s3 || '' };
    }
    if (prefix === 'E' && (ep.e1 || ep.e2 || ep.e3)) {
      return { e1: ep.e1 || '', e2: ep.e2 || '', e3: ep.e3 || '' };
    }
    if (prefix === 'M' && (ep.m1 || ep.m2 || ep.m3)) {
      return { m1: ep.m1 || '', m2: ep.m2 || '', m3: ep.m3 || '' };
    }
    if (ep.structured && prefix === 'S') {
      const st = ep.structured;
      const bits = [];
      if (st.hold_floor) bits.push('Hold above ₹' + st.hold_floor);
      if (st.pullback_lo && st.pullback_hi) {
        bits.push('Pullback ₹' + st.pullback_lo + '–' + st.pullback_hi);
      }
      if (st.breakdown) bits.push('Skip below ₹' + st.breakdown);
      if (bits.length) {
        return { s1: bits[0] || '', s2: bits[1] || '', s3: bits[2] || '' };
      }
    }
    if (!ep.lines) return null;
    const keys = prefix === 'E'
      ? { k1: 'e1', k2: 'e2', k3: 'e3', re: /^E[123]/i }
      : prefix === 'M'
        ? { k1: 'm1', k2: 'm2', k3: 'm3', re: /^M[123]/i }
        : { k1: 's1', k2: 's2', k3: 's3', re: /^S[123]/i };
    const o = { [keys.k1]: '', [keys.k2]: '', [keys.k3]: '' };
    ep.lines.forEach((line) => {
      const t = line.trim();
      if (/^S1|^E1|^M1/i.test(t)) o[keys.k1] = t.replace(/^\s*[SEM][123][^:]*:\s*/i, '');
      else if (/^S2|^E2|^M2/i.test(t)) o[keys.k2] = t.replace(/^\s*[SEM][123][^:]*:\s*/i, '');
      else if (/^S3|^E3|^M3/i.test(t)) o[keys.k3] = t.replace(/^\s*[SEM][123][^:]*:\s*/i, '');
    });
    return o;
  }

  function lookupExit(code) {
    const e = (G.exitScenarios || []).find((x) => x.code === code);
    return e ? e.meaning : '';
  }

  function lookupMonitor(code) {
    const e = (G.monitorLevels || []).find((x) => x.code === code);
    return e ? e.meaning : '';
  }

  function highlightScenarioNums(text) {
    if (text == null || text === '') return '';
    let s = esc(String(text));
    s = s.replace(
      /(\d[\d,]*(?:\.\d+)?)\s*[–-]\s*(\d[\d,]*(?:\.\d+)?)/g,
      '<span class="sc-num">$1</span>–<span class="sc-num">$2</span>',
    );
    s = s.replace(/₹[\d,]+(?:\.\d+)?/g, function (m) {
      return '<span class="sc-num">' + m + '</span>';
    });
    s = s.replace(/\b(\d[\d,]*(?:\.\d+)?)%/g, '<span class="sc-num sc-pct">$1%</span>');
    s = s.replace(/\b(\d+)\s*sh\b/gi, '<span class="sc-num sc-qty">$1 sh</span>');
    return s;
  }

  function scenarioBlockHTML(ep, prefix, labels) {
    const p = parseScenarios(ep, prefix);
    if (!p) return '';
    const k1 = prefix === 'E' ? 'e1' : prefix === 'M' ? 'm1' : 's1';
    const k2 = prefix === 'E' ? 'e2' : prefix === 'M' ? 'm2' : 's2';
    const k3 = prefix === 'E' ? 'e3' : prefix === 'M' ? 'm3' : 's3';
    if (!p[k1] && !p[k2] && !p[k3]) return '';
    let h = '<div class="scenarios">';
    if (p[k1]) {
      h += '<div class="sc"><b>' + esc(labels[0]) + '</b><span class="sc-hint">' + esc(labels[3] || '') + '</span>' +
        highlightScenarioNums(p[k1]) + '</div>';
    }
    if (p[k2]) {
      h += '<div class="sc"><b>' + esc(labels[1]) + '</b><span class="sc-hint">' + esc(labels[4] || '') + '</span>' +
        highlightScenarioNums(p[k2]) + '</div>';
    }
    if (p[k3]) {
      h += '<div class="sc"><b>' + esc(labels[2]) + '</b><span class="sc-hint">' + esc(labels[5] || '') + '</span>' +
        highlightScenarioNums(p[k3]) + '</div>';
    }
    return h + '</div>';
  }

  function allScenariosHTML(item) {
    let h = '';
    if (item.entryScenariosRef) {
      h += '<div class="scenarios-ref">' + esc(item.entryScenariosRef) + '</div>';
    }
    h += scenarioBlockHTML(item.entryScenarios, 'S', [
      'S1 · Hold', 'S2 · Pullback', 'S3 · Skip',
      lookupEntry('S1'), lookupEntry('S2'), lookupEntry('S3'),
    ]);
    h += scenarioBlockHTML(item.exitScenarios, 'E', [
      'E1 · Open', 'E2 · Bounce', 'E3 · Defer',
      lookupExit('E1'), lookupExit('E2'), lookupExit('E3'),
    ]);
    h += scenarioBlockHTML(item.monitorScenarios, 'M', [
      'M1 · Hold', 'M2 · Review', 'M3 · Alert',
      lookupMonitor('M1'), lookupMonitor('M2'), lookupMonitor('M3'),
    ]);
    return h;
  }

  function scenarioHTML(ep) {
    return scenarioBlockHTML(ep, 'S', [
      'S1 · Hold', 'S2 · Pullback', 'S3 · Skip',
      lookupEntry('S1'), lookupEntry('S2'), lookupEntry('S3'),
    ]);
  }

  function scoreCellHTML(item) {
    let h = '';
    if (item.v2Score != null && item.v2Score !== '') {
      h += 'V2 <b>' + esc(item.v2Score) + '</b>';
    } else if (item.score != null && item.score !== '') {
      h += 'S <b>' + esc(item.score) + '</b>';
    }
    if (item.adjScore != null && item.adjScore !== '') {
      h += (h ? ' · ' : '') + 'Adj ' + esc(item.adjScore);
    }
    if (item.sector) {
      h += '<div class="sub">' + esc(item.sector) + '</div>';
    }
    return h || '—';
  }

  function stockRowHTML(item) {
    const pnl = formatPnlSpan(holdingPnlPct(item) != null ? holdingPnlPct(item) : item.pnlPct);
    const amt = item.amount || (item.value ? fmt(item.value) : (item.detail || '').match(/₹[\d.kL]+/)?.[0] || '—');
    const whenText = item.when || '—';
    const hasDate = whenText.includes('Wed') || whenText.includes('Mon') || whenText.includes('Thu') || whenText.includes('Fri') || whenText.includes('Tue');
    const whenHtml = hasDate ? '<b>' + esc(whenText) + '</b>' : esc(whenText);
    const amtHtml = amt !== '—' ? '<b>' + esc(amt) + '</b>' : '—';
    let stopHtml;
    if (gttStopInfo(item)) {
      stopHtml = stopDisplayHTML(item);
    } else if (item.stopLoss) {
      stopHtml = '<span style="color:var(--sell)">Stop ₹' + item.stopLoss.toLocaleString() + '</span>';
    } else {
      stopHtml = esc(riskMetaHTML(item));
    }
    return (
      '<tr><td class="sym">' + stockCellHTML(item) + '</td>' +
      '<td class="' + actionClass(item.action) + '">' + esc(actionLabel(item.action)) + '</td>' +
      '<td class="when-col">' + whenHtml + '</td>' +
      '<td class="score-col">' + scoreCellHTML(item) + '</td>' +
      '<td class="price-col">' + priceCellHTML(item) + '</td>' +
      '<td>' + amtHtml + allScenariosHTML(item) + '</td>' +
      '<td>' + pnl + '</td>' +
      '<td class="risk-meta">' + stopHtml + '</td>' +
      '<td>' + whyCellHTML(item) + '</td></tr>'
    );
  }

  function renderStockTable(sec) {
    if (sec.kind === 'footer' && sec.finalNumbers) {
      const fn = sec.finalNumbers;
      let h = '<div class="totals">';
      h += totalBox('Sells', fmt(fn.sellProceeds), 'sell');
      h += totalBox('Buys', fmt(fn.buyOrders), 'buy');
      h += totalBox('Net cash', fmt(fn.netMin), fn.netMin <= 0 ? 'buy' : 'sell');
      h += totalBox('Portfolio', fmt(D.portfolioValue), '');
      h += '</div>';
      const tax = sec.taxHarvest || D.taxHarvest;
      if (tax && (tax.losses || tax.gains || tax.netPnl)) {
        h += '<div class="guide-run" style="margin-top:14px"><b>Tax-loss harvest</b><br>';
        h += 'Losses (offset): ' + fmt(tax.losses) + ' · Gains: ' + fmt(tax.gains);
        h += ' · Net: ' + fmt(tax.netPnl) + ' · Est. STCG tax: ' + fmt(tax.taxPayable || 0);
        if (tax.note) h += '<br><span class="sub">' + esc(tax.note) + '</span>';
        h += '</div>';
      }
      const risk = sec.riskProfile || D.riskProfile;
      if (risk && risk.portfolioValue) {
        h += '<div class="guide-run" style="margin-top:10px"><b>Portfolio risk</b><br>';
        h += 'Value ' + fmt(risk.portfolioValue) + ' · Vol ' + esc(String(risk.volatilityPct)) + '%';
        h += ' · 1d VaR (95%): ' + fmt(risk.var95);
        if (risk.worstSymbol) {
          h += ' · Worst: ' + esc(risk.worstSymbol) + ' (' + esc(String(risk.worstPnlPct)) + '%)';
        }
        h += '</div>';
      }
      if (fn.budgetNote) h += '<p class="guide-run" style="margin-top:14px"><b>Note:</b> ' + esc(fn.budgetNote) + '</p>';
      return h;
    }

    if (sec.grouped) {
      let h = '';
      sec.grouped.forEach((cat) => {
        h += '<div class="grp-label">[' + esc(cat.code) + '] ' + esc(cat.label) + '</div>';
        h += '<table class="stock-table"><thead><tr><th>Stock</th><th>Action</th><th>When</th><th>Score</th><th>Price</th><th>Amount</th><th>P&L</th><th>Risk</th><th>Why</th></tr></thead><tbody>';
        cat.stocks.forEach((s) => { h += stockRowHTML(s); });
        h += '</tbody></table>';
      });
      return h;
    }

    const items = sec.items || [];
    if (sec.id === 'radar' && items.length) {
      let h = '<table class="stock-table"><thead><tr><th>Stock</th><th>Tier</th><th>Price</th><th>Setup</th><th>Monday trigger</th></tr></thead><tbody>';
      items.forEach((r) => {
        const tierPlain = r.tierPlain || lookupTier(r.tier);
        const reasonPlain = r.reasonPlain || r.reason || '—';
        const trigPlain = r.triggerPlain || r.trigger || '—';
        h += '<tr><td class="sym">' + stockCellHTML(r) + '</td><td class="tier-cell">' +
          codeChip(r.tier, tierPlain, 'tier') + '</td>' +
          '<td class="price-col">' + priceCellHTML(r) + '</td>' +
          '<td class="plain">' + esc(reasonPlain) +
          (r.reason && r.reason !== reasonPlain ? '<div class="raw">' + esc(r.reason) + '</div>' : '') +
          allScenariosHTML(r) + '</td>' +
          '<td><div class="plain">' + esc(trigPlain) + '</div>' +
          (r.trigger && r.trigger !== trigPlain ? '<div class="raw">' + esc(r.trigger) + '</div>' : '') + '</td></tr>';
      });
      return h + '</tbody></table>';
    }

    if (!items.length) {
      return '<div class="empty-msg">Nothing in this section for this run.</div>';
    }

    let h = '<table class="stock-table"><thead><tr><th>Stock</th><th>Action</th><th>When</th><th>Score</th><th>Price</th><th>Amount / Entry</th><th>P&L</th><th>Risk</th><th>Why (REASON)</th></tr></thead><tbody>';
    items.forEach((it) => { h += stockRowHTML(it); });
    return h + '</tbody></table>';
  }

  function totalBox(l, v, cls) {
    return '<div class="total-box"><small>' + l + '</small><b' + (cls === 'sell' ? ' style="color:var(--sell)"' : cls === 'buy' ? ' style="color:var(--buy)"' : '') + '>' + v + '</b></div>';
  }

  function badgeFor(sec) {
    const sev = SEV[sec.id] || 'neutral';
    if (sec.totalValue) return '<span class="sec-badge neutral">' + esc(sec.totalValue) + '</span>';
    if (sev === 'sell') return '<span class="sec-badge sell">Exit</span>';
    if (sev === 'buy') return '<span class="sec-badge buy">Entry</span>';
    if (sev === 'warn') return '<span class="sec-badge warn">Monitor</span>';
    return '<span class="sec-badge neutral">Info</span>';
  }

  function vizFlowBar(label, val, max, cls) {
    const h = Math.round((val / max) * 56 + 10);
    return '<div class="vbar-wrap">' +
      '<div class="vbar ' + cls + '" style="height:' + h + 'px" title="' + esc(label) + ': ' + fmt(val) + '"></div>' +
      '<span class="vbar-lbl">' + esc(label) + '</span>' +
      '<span class="vbar-val">' + fmt(val) + '</span></div>';
  }

  function renderVizCard() {
    const fn = D.finalNumbers || {};
    const el = $('viz-card');
    if (!el) return;
    const sell = Math.abs(Number(fn.sellProceeds) || 0);
    const buy = Math.abs(Number(fn.buyOrders) || 0);
    const net = Math.abs(Number(fn.netMin) || 0);
    const max = Math.max(sell, buy, net, 1);

    let flow =
      '<div class="viz-panel"><div class="viz-title">Cash flow this week</div>' +
      '<div class="viz-bars-labeled">' +
      vizFlowBar('Sells', sell, max, 'sell') +
      vizFlowBar('Net deploy', net, max, 'net') +
      vizFlowBar('Buys', buy, max, 'buy') +
      '</div></div>';

    const sectors = (D.sectorChart || []).slice(0, 6);
    let sect = '';
    if (sectors.length) {
      const smax = Math.max.apply(null, sectors.map((s) => Number(s.value) || 0).concat([1]));
      sect = '<div class="viz-panel"><div class="viz-title">Holdings by sector</div><div class="sector-bars">';
      sectors.forEach((s) => {
        const val = Number(s.value) || 0;
        const pct = Math.round((val / smax) * 100);
        sect += '<div class="sector-row"><span class="sector-name">' + esc(s.name) + '</span>' +
          '<div class="sector-track"><div class="sector-fill" style="width:' + pct + '%"></div></div>' +
          '<span class="sector-val">' + fmt(val) + '</span></div>';
      });
      sect += '</div></div>';
    } else {
      sect = '<div class="viz-panel viz-panel-empty"><div class="viz-title">Holdings by sector</div>' +
        '<p class="empty-msg" style="padding:12px 0">No sector breakdown</p></div>';
    }
    el.innerHTML = flow + sect;
  }

  function renderMetricRow() {
    const fn = D.finalNumbers || {};
    const { sellN, buyN } = countActions();
    const surplus = fn.netMin <= 0;
    $('metric-row').innerHTML =
      metricCard('Portfolio value', fmt(D.portfolioValue), D.positions + ' holdings') +
      metricCard('Sell proceeds', fmt(fn.sellProceeds), sellN + ' exits', true) +
      metricCard('Buy orders', fmt(fn.buyOrders), buyN + ' entries') +
      metricCard('Net cash', fmt(fn.netMin), surplus ? 'Surplus' : 'Deploy', surplus, !surplus);
  }

  function metricCard(label, val, sub, positive, negative) {
    const delta = positive ? 'm-delta' : (negative ? 'm-delta neg' : 'm-delta');
    return '<div class="metric-card"><div class="m-label">' + label + '</div><div class="m-value">' + val + '</div><div class="' + delta + '">' + esc(sub) + '</div></div>';
  }

  function renderMiniRow() {
    const fn = D.finalNumbers || {};
    const { sellN, buyN } = countActions();
    $('mini-row').innerHTML =
      '<div class="mini-pill"><span class="dot sell"></span>Sells <b>' + sellN + '</b></div>' +
      '<div class="mini-pill"><span class="dot buy"></span>Buys <b>' + buyN + '</b></div>' +
      '<div class="mini-pill"><span class="dot lime"></span>Holdings <b>' + D.positions + '</b></div>' +
      (fn.budgetNote ? '<div class="mini-pill">' + esc(fn.budgetNote) + '</div>' : '');
  }

  function renderSections() {
    const sections = visibleSections();
    const root = $('sections-root');
    if (!root) return;

    let body = '';
    sections.forEach((sec) => {
      const sev = SEV[sec.id] || 'neutral';
      const collapsed = isSectionCollapsed(sec.id);
      body += '<section class="brief-section sev-' + sev + (collapsed ? ' collapsed' : '') +
        '" id="sec-' + esc(sec.id) + '" data-sec-id="' + esc(sec.id) + '">';
      body += '<div class="sec-head">';
      body += '<button type="button" class="sec-toggle" aria-expanded="' + (!collapsed) +
        '" title="' + (collapsed ? 'Expand section' : 'Minimize section') + '">' +
        '<span class="sec-toggle-icon">' + (collapsed ? '▸' : '▾') + '</span></button>';
      body += '<span class="sec-num">' + esc(sectionNumLabel(sec)) + '</span>';
      body += '<div class="sec-head-text"><h2>' + esc(sec.headline) + '</h2>';
      if (sec.subhead) body += '<div class="sec-meta">' + esc(sec.subhead) + '</div>';
      body += '</div>' + badgeFor(sec) + '</div>';
      body += '<div class="sec-body">';
      body += vmqSellNote(sec);
      if (sec.note) body += '<p class="sec-note">' + esc(sec.note) + '</p>';
      body += renderStockTable(sec);
      body += '</div></section>';
    });
    root.innerHTML = body;
  }

  function renderHeader() {
    const reportName = (D.report || '').replace('Enhanced_Stock_Report_', '').replace('.xlsx', '');
    const strat = D.activeStrategy || 'QMST';
    let meta = strat + ' · ';
    if (D.reportPath) {
      meta += '<button type="button" class="report-link report-copy" data-report-path="' +
        esc(D.reportPath) + '" title="Click to copy full path: ' + esc(D.reportPath) + '">' +
        esc(reportName) + '</button>';
    } else {
      meta += esc(reportName);
    }
    $('run-meta').innerHTML = meta;

    const regime = String(D.regime || 'Sideways').toLowerCase();
    const rc = $('regime-chip');
    rc.className = 'pill-select ' + (regime.includes('bull') ? 'bull' : regime.includes('bear') ? 'bear' : 'side');
    rc.textContent = D.regime + ' market';

    const sells = [];
    const buys = [];
    visibleSections().forEach((sec) => {
      const id = sec.id || '';
      if (id === 'swap') {
        sectionItems(sec).forEach((item) => {
          if (item.stock) sells.push(item.stock);
          if (item.targetSymbol) buys.push(item.targetSymbol);
        });
        return;
      }
      runSymbols(sec).forEach((s) => {
        if (/sell|exit|lvmrot/.test(id)) sells.push(s);
        if (/buynew|increase/.test(id)) buys.push(s);
      });
    });
    const u = (a) => [...new Set(a)];
    const fn = D.finalNumbers || {};
    let summary = '';
    if (u(sells).length) summary += 'Sell <em>' + esc(u(sells).slice(0, 4).join(', ')) + '</em>';
    if (u(buys).length) summary += (summary ? ' · ' : '') + 'Buy <em>' + esc(u(buys).join(', ')) + '</em>';
    if (fn.budgetNote) summary += (summary ? ' · ' : '') + esc(fn.budgetNote);
    if (!summary) summary = 'Stable week — check <em>Holdings</em> for positions you keep.';
    $('plain-summary').innerHTML = summary;
  }

  function stat(l, v, cls) {
    return '<div class="hstat' + (cls ? ' ' + cls : '') + '"><b>' + v + '</b><small>' + l + '</small></div>';
  }

  function holdingDetailHTML(r) {
    if (!r.summaryLine && !r.monitorScenarios) return '';
    const sym = esc(String(r.stock).toLowerCase());
    let h = '<tr class="hold-detail collapsed" data-h="' + sym + '"><td colspan="10">';
    h += '<button type="button" class="hold-toggle" data-h="' + sym + '" aria-expanded="false">';
    h += '<span class="hold-toggle-icon">▸</span> Monitor levels</button>';
    h += '<div class="hold-detail-body">';
    if (r.summaryLine) {
      h += '<div class="hold-summary">' + highlightScenarioNums(r.summaryLine) + '</div>';
    }
    if (r.monitorScenarios) {
      h += scenarioBlockHTML(r.monitorScenarios, 'M', [
        'M1 · Hold', 'M2 · Review', 'M3 · Alert',
        lookupMonitor('M1'), lookupMonitor('M2'), lookupMonitor('M3'),
      ]);
    }
    return h + '</div></td></tr>';
  }

  function renderHoldings() {
    const el = $('holdings-content');
    const rows = sortHoldings(D.holdings || []);
    if (!rows.length) { el.innerHTML = '<div class="empty-msg">No holdings.</div>'; return; }

    let h = '<table class="stock-table" id="holdings-table"><thead><tr><th>Stock</th><th>Action</th><th>Value</th><th>Price</th><th>P&L</th><th>Qty</th><th>Score</th><th>Sector</th><th>Stop</th><th>Reason</th></tr></thead><tbody>';
    let lastRank = -1;
    rows.forEach((r) => {
      const rank = holdingActionRank(r.action);
      if (rank !== lastRank) {
        h += '<tr class="hold-grp"><td colspan="10">' + esc(holdingActionGroupLabel(rank)) + '</td></tr>';
        lastRank = rank;
      }
      const pnl = formatPnlSpan(holdingPnlPct(r));
      const score = r.v2Score != null ? 'V2 ' + r.v2Score : (r.score != null ? String(r.score) : '—');
      h += '<tr data-h="' + esc(String(r.stock).toLowerCase()) + '"><td class="sym">' + stockCellHTML(r) + '</td><td class="' +
        actionClass(r.action) + '">' + esc(actionLabel(r.action || 'HOLD')) + '</td><td>' + fmt(r.value) + '</td><td class="price-col">' +
        priceCellHTML(r) + '</td><td>' + pnl + '</td><td>' +
        esc(r.qty != null ? String(r.qty) : '—') + '</td><td>' + esc(score) + '</td><td>' + esc(r.sector || '—') + '</td><td>' +
        stopDisplayHTML(r) + '</td><td class="plain">' +
        esc(r.reasonPlain || decodeReasonPlain(r.reason) || r.reason || '—') + '</td></tr>';
      h += holdingDetailHTML(r);
    });
    el.innerHTML = h + '</tbody></table>';
  }

  function glossaryTable(title, rows, colA, colB) {
    if (!rows || !rows.length) return '';
    let h = '<div class="guide-table-wrap"><div class="guide-table-title">' + esc(title) + '</div>';
    h += '<table class="guide-table"><thead><tr><th>' + esc(colA) + '</th><th>' + esc(colB) + '</th></tr></thead><tbody>';
    rows.forEach((r) => {
      const a = r.code || r.tier || r.pattern || r.abbr || r.label || '';
      const b = r.meaning || r.plain || '';
      h += '<tr><td>' + esc(a) + '</td><td>' + esc(b) + '</td></tr>';
    });
    return h + '</tbody></table></div>';
  }

  function renderLvmTop10() {
    const picks = D.lvmTop10 || [];
    if (!picks.length) return;
    const root = $('sections-root');
    if (!root) return;
    const hasStab = picks.some((p) => p.stability != null);
    const el = document.createElement('section');
    el.className = 'brief-section sev-neutral';
    el.id = 'sec-lvmtop10';
    el.setAttribute('data-sec-id', 'lvmtop10');
    let h = '<div class="sec-head">';
    h += '<span class="sec-num">LVM</span>';
    const screenN = D.lvmScreenN || 20;
    const fundN = D.lvmFundN || 12;
    h += '<div class="sec-head-text"><h2>LVM Top ' + screenN + ' — Picks + Stability Audit</h2></div></div>';
    h += '<div class="sec-body">';
    if (D.lvmDataDegraded) {
      h += '<p class="sec-note" style="color:var(--tape-warn,#c9a227);font-weight:600">LVM data incomplete — momentum columns missing. Do not trade LVM picks from this report; re-run analysis.</p>';
    }
    h += '<p class="sec-note">Screen ' + screenN + ' names (✓). <b>FUND</b> = top ' + fundN + ' funded monthly (Priority 5). Rest = watch/alternate only. Tier = stability ±2% noise (50 trials). -10% stop.</p>';
    const hasPnl = picks.some((p) => p.holdingPnl != null);
    h += '<table class="stock-table"><thead><tr><th>#</th><th>Book</th><th>Tier</th><th>Symbol</th><th>Sector</th><th>Price</th><th>LVM</th><th>12m Ret</th><th>Vol</th>';
    if (hasStab) h += '<th>Stab</th>';
    if (hasPnl) h += '<th>Held ₹</th><th>P&L</th>';
    h += '</tr></thead><tbody>';
    picks.forEach((p, i) => {
      const ret = p.return12m != null ? (p.return12m > 0 ? '+' : '') + p.return12m.toFixed(1) + '%' : '—';
      const vol = p.volatility != null ? p.volatility.toFixed(1) + '%' : '—';
      const tier = p.tier || '—';
      const alt = p.isAlternate ? ' style="opacity:0.6"' : '';
      const mark = p.isAlternate ? '' : '✓';
      const book = p.fundSlot ? 'FUND' : (p.isAlternate ? 'ALT' : '—');
      const stabTxt = hasStab && p.stability != null ? p.stability + '/' + (p.stabilityMax || 50) : '';
      const pnlNum = p.holdingPnl != null ? p.holdingPnl : null;
      const pnlColor = pnlNum != null ? (pnlNum > 0 ? 'color:var(--buy)' : pnlNum < 0 ? 'color:var(--sell)' : '') : '';
      const pnlVal = pnlNum != null ? (pnlNum > 0 ? '+' : '') + pnlNum.toFixed(1) + '%' : '—';
      const heldVal = p.holdingValue ? '<b>' + fmt(p.holdingValue) + '</b>' : '—';
      const lvmScore = p.lvmScore ? p.lvmScore.toFixed(0) : '—';
      const symLink = '<a href="' + tvUrl(p.stock) + '" target="_blank" rel="noopener" class="sym-name" title="TradingView">' + esc(p.stock) + '</a>';
      const coLink = p.company ? '<a href="' + screenerUrl(p.stock) + '" target="_blank" rel="noopener" class="sym-co" title="Screener">' + esc(p.company) + '</a>' : '';
      h += '<tr' + alt + '><td>' + mark + (i + 1) + '</td><td>' + esc(book) + '</td><td>' + esc(tier) + '</td><td>' + symLink + (coLink ? '<br>' + coLink : '') + '</td><td>' + esc(p.sector) + '</td><td>' + fmt(p.price) + '</td><td>' + lvmScore + '</td><td>' + ret + '</td><td>' + vol + '</td>';
      if (hasStab) h += '<td>' + stabTxt + '</td>';
      if (hasPnl) h += '<td>' + heldVal + '</td><td style="' + pnlColor + '">' + pnlVal + '</td>';
      h += '</tr>';
    });
    h += '</tbody></table></div>';
    el.innerHTML = h;
    root.appendChild(el);
  }

  function renderRsiPullback() {
    const picks = D.rsiPullback || [];
    if (!picks.length) return;
    if (visibleSections().some((s) => s.id === 'rsipullback')) return;
    const root = $('sections-root');
    if (!root) return;
    const el = document.createElement('section');
    el.className = 'brief-section sev-info';
    el.id = 'sec-rsipullback';
    el.setAttribute('data-sec-id', 'rsipullback');
    let h = '<div class="sec-head">';
    h += '<span class="sec-num">P5.5</span>';
    h += '<div class="sec-head-text"><h2>RSI Pullback — Weekly Trades (5-day hold, -3% stop)</h2></div></div>';
    h += '<div class="sec-body">';
    h += '<p class="sec-note">Buy closest to RSI 40, hold 5 days, -3% stop. 60% WR proven.</p>';
    h += '<table class="stock-table"><thead><tr><th>Symbol</th><th>Price</th><th>RSI</th><th>Dist to 40</th><th>Above SMA50</th><th>Stop -3%</th></tr></thead><tbody>';
    picks.forEach((p) => {
      const stop = (p.price * 0.97).toFixed(1);
      h += '<tr><td><b>' + esc(p.stock) + '</b></td><td>' + fmt(p.price) + '</td><td>' + (p.rsi || 0).toFixed(1) + '</td><td>' + (p.distTo40 || 0).toFixed(1) + '</td><td>' + (p.aboveSma50Pct > 0 ? '+' : '') + (p.aboveSma50Pct || 0).toFixed(1) + '%</td><td>' + stop + '</td></tr>';
    });
    h += '</tbody></table></div>';
    el.innerHTML = h;
    root.appendChild(el);
  }

  function renderHelp() {
    const g = D.actionPlanGuide || {};
    let h = '<p class="guide-callout rule"><b>Rule:</b> ' + esc(g.readingRule || '') + '</p>';
    h += glossaryTable('Breakout radar tiers', g.radarTiers, 'Tier', 'Meaning');
    h += glossaryTable('Entry scenarios (S1 / S2 / S3)', (g.entryScenarios || []).map((e) => ({
      code: e.code + ' · ' + (e.label || ''),
      meaning: e.meaning,
    })), 'Scenario', 'Meaning');
    h += glossaryTable('SELL WHY codes', (g.sellWhyCodes || []).map((x) => ({
      code: x.code,
      meaning: x.label,
    })), 'Code', 'Meaning');
    h += glossaryTable('Common REASON text', (g.reasonPatterns || []).map((x) => ({
      code: x.pattern,
      meaning: x.plain,
    })), 'Pattern', 'Plain English');
    h += glossaryTable('Radar row shorthand', g.radarFieldHints, 'Term', 'Meaning');
    h += glossaryTable('Monday trigger phrases', g.triggerHints, 'Phrase', 'Meaning');
    h += '<p class="guide-callout" style="margin-top:12px">Action Plan shows trades only. Holdings includes HOLD monitor levels (Hold / Review / Alert). LVM mode: GTT stop in the Stop column. Full VMQ and dual strategy remain in Excel and terminal.</p>';
    $('help-body').innerHTML = h;
  }

  function setSimpleView(on) {
    simpleView = on;
    document.body.classList.toggle('simple-view', on);
    localStorage.setItem(LS.simpleView, on ? 'true' : 'false');
    const btn = $('toggle-simple');
    if (btn) btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  function switchView(v) {
    document.querySelectorAll('.rail-btn[data-view]').forEach((t) => {
      t.classList.toggle('active', t.getAttribute('data-view') === v);
    });
    document.querySelectorAll('.pane').forEach((p) => p.classList.toggle('active', p.id === 'view-' + v));
  }

  function openHelp() { $('help-panel').hidden = false; }
  function closeHelp() { $('help-panel').hidden = true; }

  renderHeader();
  renderVizCard();
  renderMetricRow();
  renderMiniRow();
  renderSections();
  renderHoldings();
  renderLvmTop10();
  renderRsiPullback();
  renderHelp();
  setSimpleView(simpleView);

  document.querySelectorAll('.rail-btn[data-view]').forEach((t) => {
    t.addEventListener('click', () => switchView(t.getAttribute('data-view')));
  });
  $('toggle-simple').addEventListener('click', () => setSimpleView(!simpleView));
  $('help-open-rail').addEventListener('click', openHelp);
  $('fab-help').addEventListener('click', openHelp);
  $('help-close').addEventListener('click', closeHelp);
  $('help-panel').addEventListener('click', (e) => { if (e.target.id === 'help-panel') closeHelp(); });
  $('holdings-search')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('#holdings-table tbody tr[data-h]').forEach((tr) => {
      const sym = tr.getAttribute('data-h') || '';
      const show = !q || sym.includes(q);
      tr.style.display = show ? '' : 'none';
      const next = tr.nextElementSibling;
      if (next && next.classList.contains('hold-detail') && next.getAttribute('data-h') === sym) {
        next.style.display = show ? '' : 'none';
      }
    });
    document.querySelectorAll('#holdings-table tbody tr.hold-grp').forEach((grp) => {
      let row = grp.nextElementSibling;
      let any = false;
      while (row && !row.classList.contains('hold-grp')) {
        if (row.hasAttribute('data-h') && row.style.display !== 'none') any = true;
        row = row.nextElementSibling;
      }
      grp.style.display = any ? '' : 'none';
    });
  });

  document.getElementById('holdings-content')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.hold-toggle');
    if (!btn) return;
    const row = btn.closest('.hold-detail');
    if (!row) return;
    const open = row.classList.toggle('collapsed');
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    btn.querySelector('.hold-toggle-icon').textContent = open ? '▸' : '▾';
  });

  $('sections-root')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.sec-toggle');
    if (!btn) return;
    const sec = btn.closest('.brief-section');
    if (!sec) return;
    const secId = sec.getAttribute('data-sec-id');
    if (!secId) return;
    const collapsed = sec.classList.toggle('collapsed');
    btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    btn.setAttribute('title', collapsed ? 'Expand section' : 'Minimize section');
    btn.querySelector('.sec-toggle-icon').textContent = collapsed ? '▸' : '▾';
    sectionCollapsedState[secId] = collapsed;
    saveSectionCollapsedState(sectionCollapsedState);
  });

  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    e.preventDefault();
    copySymbol(btn.getAttribute('data-copy') || btn.textContent.trim(), btn);
  });

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.report-copy');
    if (!btn) return;
    const path = btn.getAttribute('data-report-path') || '';
    if (!path) return;
    copySymbol(path, btn);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeHelp();
    if (e.target.matches('input')) return;
    if (e.key === '1') switchView('plan');
    if (e.key === '2') switchView('holdings');
  });

  (function dashboardAutoReload() {
    if (!/^127\.0\.0\.1$|^localhost$/i.test(location.hostname)) return;
    const startVersion = (window.DASHBOARD_DATA && window.DASHBOARD_DATA.buildVersion) || '';
    if (!startVersion) return;
    setInterval(function () {
      fetch('/api/version', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (v) {
          if (v.version && v.version !== startVersion) location.reload();
        })
        .catch(function () {});
    }, 2500);
  })();
})();
