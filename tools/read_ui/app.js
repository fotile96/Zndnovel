'use strict';
// 通读 UI 的前端。只 GET，不 POST——本工具不写任何东西。
//
// 渲染策略：**按单元流式追加**。全书 16693 行一次性塞进 DOM 会让浏览器爬，
// 所以每次只渲染一个演出单元（几行到两三百行），滚到底自动接下一个，
// 点目录则清空重来。这样既能真正"从头读到尾"，DOM 又始终有界。

const $ = (s) => document.querySelector(s);
const S = { outline: [], units: {}, loaded: [], cur: null, filtered: false, busy: false };

const esc = (s) => (s == null ? '' : String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])));

// 控制码与说话人前缀染色：_n/_r 是引擎的换行符，读的时候要看得见但别抢戏；
// 【名字】是说话人位，标出来能让两栏对读时一眼对齐。
function fmt(s) {
  let h = esc(s);
  h = h.replace(/^【([^】]*)】/, '<span class="spk">【$1】</span>');
  h = h.replace(/_n|_r/g, (m) => `<span class="ctl">${m}</span>`);
  return h;
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

// ---- 左边栏 ----

function renderOutline() {
  const box = $('#outline');
  box.innerHTML = '';
  let chapter = null;
  for (const u of S.outline) {
    if (u.type === 'unit' && u.chapter && u.chapter !== chapter) {
      chapter = u.chapter;
      const h = document.createElement('div');
      h.className = 'ch'; h.textContent = chapter;
      box.appendChild(h);
    }
    const d = document.createElement('div');
    d.dataset.seq = u.seq;
    if (u.type === 'marker') {
      d.className = 'ou marker';
      d.innerHTML = `<span class="sq mono">${u.seq}</span><span class="ti">${esc(u.text)}</span>`;
    } else {
      d.className = `ou k-${u.unit_kind || ''}`;
      d.innerHTML = `<span class="sq mono">${u.seq}</span>`
        + `<span class="ti">${esc(u.title || u.state || '')}`
        + `${u.title_zh ? `<span class="tz">${esc(u.title_zh)}</span>` : ''}</span>`
        + `<span class="nn mono">${u.n_lines}</span>`;
      d.title = `${u.src || ''} / ${u.state || ''}${u.title_zh ? ' / ' + u.title_zh : ''}`;
    }
    d.onclick = () => jumpTo(u.seq);
    box.appendChild(d);
  }
}

function markOutline(seq) {
  document.querySelectorAll('.ou.on').forEach((e) => e.classList.remove('on'));
  const e = document.querySelector(`.ou[data-seq="${seq}"]`);
  if (e) { e.classList.add('on'); e.scrollIntoView({ block: 'nearest' }); }
}

// ---- 正文 ----

function unitNode(u) {
  const wrap = document.createElement('section');
  wrap.dataset.seq = u.seq;
  if (u.type === 'marker') {
    wrap.className = 'mk';
    wrap.innerHTML = `${esc(u.text)}${u.recap ? `<span class="re">${esc(u.recap)}</span>` : ''}`;
    return wrap;
  }
  const head = document.createElement('div');
  head.className = 'uhead';
  head.innerHTML = `<span class="sq mono">#${u.seq}</span>`
    + `<h2>${esc(u.title || u.state || '')}</h2>`
    + `${u.title_zh ? `<span class="tzh">${esc(u.title_zh)}</span>` : ''}`
    + `<span class="chip k-${u.unit_kind}">${esc(u.unit_kind)}</span>`
    + `<span class="meta mono">${esc(u.src || '')} · ${esc(u.state || '')} · ${u.n_lines} 行</span>`;
  wrap.appendChild(head);

  const body = document.createElement('div');
  body.className = 'lines';
  for (const ln of u.lines) body.appendChild(rowNode(ln));
  wrap.appendChild(body);
  return wrap;
}

function rowNode(ln) {
  const row = document.createElement('div');
  row.className = 'row' + (ln.revised ? ' rev' : '') + (ln.pending ? ' pend' : '');
  row.dataset.id = ln.id;
  const nAnn = ln.history.length + ln.decisions.length;
  // 有未清关修改时，右栏显示的是**改后**的文字（划掉现值），因为读的人想看的
  // 是自己改成了什么；现值仍在同一格里留着，免得改完就看不见原样了。
  const zhCell = ln.pending
    ? `<div class="zh"><span class="was">${fmt(ln.zh)}</span>`
      + `<span class="now">${fmt(ln.pending.zh)}</span>`
      + `${ln.pending.stale ? '<span class="warn">⚠ 你改完之后这行又被别处动过</span>' : ''}</div>`
    : `<div class="zh${ln.zh ? '' : ' empty'}">${ln.zh ? fmt(ln.zh) : '（未翻译）'}</div>`;
  row.innerHTML =
    `<div class="no mono" title="${nAnn ? nAnn + ' 条修订/裁决记录' : ''}点击展开／编辑">`
    + `${ln.pending ? '<span class="pen">✎</span>' : (ln.revised ? '<span class="dot">●</span>' : '')}`
    + `${ln.id}</div>`
    + `<div class="jp">${fmt(ln.jp)}</div>` + zhCell;
  row.querySelector('.no').onclick = () => toggleAnn(row, ln);
  return row;
}

function toggleAnn(row, ln) {
  const open = row.nextElementSibling;
  if (open && open.classList.contains('ann')) { open.remove(); return; }
  const a = document.createElement('div');
  a.className = 'ann';
  const bits = [];
  bits.push(`<div class="kv mono">${esc(ln.file || '')} · ${esc(ln.func || '')}`
    + ` · 语音 ${esc(ln.voice || '—')} · ${esc(ln.kind || '')}</div>`);
  if (ln.first_meta) {
    const m = ln.first_meta;
    bits.push(`<div><h4>首译</h4><div>${fmt(ln.first_zh)}</div>`
      + `<div class="kv mono">${esc(m.model || '')} · 批 ${esc(m.batch)} · v${esc(m.glossary_v)} · ${esc(m.ts)}</div></div>`);
  }
  if (ln.history.length) {
    // v19 C1 的片假名→罗马音是一次机械全库改名，占全部修订步的一半以上。
    // 默认折叠，但**照常计数并可展开**——藏起来不算数就成了假的修订史。
    const step = (h) => {
      const pv = h.prov ? ` · ${esc(h.prov.channel || '')}${h.prov.seg ? ' @' + esc(h.prov.seg) : ''}`
        + (h.prov.retract ? ' · 撤回' : '') : '';
      return `<div class="hstep${h.c1_rename ? ' c1' : ''}"><div class="fr">${fmt(h.prev)}</div>`
        + `<div class="to">${fmt(h.zh)}</div>`
        + `<div class="kv mono">${esc(h.reason)} · v${esc(h.glossary_v)} · ${esc(h.ts)}${pv}`
        + `${h.c1_rename ? ' · 仅罗马音化' : ''}</div></div>`;
    };
    const shown = ln.history.filter((h) => !h.c1_rename).map(step).join('');
    const hidden = ln.history.filter((h) => h.c1_rename).map(step).join('');
    const n = ln.history.length;
    const head = ln.c1_hidden
      ? `修订史 ${n} 步<button class="unfold" data-n="${ln.c1_hidden}">`
        + `（其中 ${ln.c1_hidden} 步仅片假名→罗马音，已折叠 · 点开）</button>`
      : `修订史 ${n} 步`;
    bits.push(`<div><h4>${head}</h4>${shown}`
      + (hidden ? `<div class="c1box" hidden>${hidden}</div>` : '') + `</div>`);
  }
  if (ln.decisions.length) {
    const ds = ln.decisions.map((d) => `<div class="dec">`
      + `<div class="kv mono">${esc(d.seg)} · ${esc(d.verdict)}`
      + `${d.chosen_channel ? ' · ' + esc(d.chosen_channel) : ''}`
      + `${d.reason_code ? ' · ' + esc(d.reason_code) : ''} · ${esc(d.ts)}</div>`
      + (d.note ? `<div class="note">${esc(d.note)}</div>` : '') + `</div>`).join('');
    bits.push(`<div><h4>人裁记录 ${ln.decisions.length} 条</h4>${ds}</div>`);
  }
  // 编辑区放在批注面最下方——先看清这一行的来历（首译、修订史、人裁），
  // 再决定要不要动它。
  const cur = ln.pending ? ln.pending.zh : ln.zh;
  bits.push(`<div class="editbox"><h4>人工修改<span class="hintline">`
    + `原样保存，不清洗；只落草稿，进生产要另跑 <code>tools/read_commit.py</code></span></h4>`
    + `<textarea class="ed" rows="2" spellcheck="false">${esc(cur)}</textarea>`
    + `<input class="ednote" placeholder="批注（可空）" value="${esc(ln.pending ? ln.pending.note : '')}">`
    + `<div class="edbar"><button class="save">保存到草稿</button>`
    + `<button class="reset">还原成现行译文</button>`
    + `<span class="edmsg"></span></div>`
    + `<div class="edwarn"></div></div>`);

  a.innerHTML = bits.join('');
  wireEditor(a, ln);
  const btn = a.querySelector('.unfold');
  if (btn) btn.onclick = () => {
    const box = a.querySelector('.c1box');
    box.hidden = !box.hidden;
    btn.textContent = box.hidden
      ? `（其中 ${btn.dataset.n} 步仅片假名→罗马音，已折叠 · 点开）`
      : `（收起那 ${btn.dataset.n} 步机械改名）`;
  };
  row.after(a);
}

function renderWarnings(box, ws) {
  box.innerHTML = ws && ws.length
    ? `<div class="wl"><b>机械体检</b>${ws.map((w) => `<div>· ${esc(w)}</div>`).join('')}`
      + `<div class="wnote">顾问级——草稿照存；但 <code>read_commit</code> 默认会拦下有警告的行。</div></div>`
    : '';
}

function wireEditor(a, ln) {
  const ed = a.querySelector('.ed');
  const note = a.querySelector('.ednote');
  const msg = a.querySelector('.edmsg');
  const warn = a.querySelector('.edwarn');
  if (ln.pending) renderWarnings(warn, ln.pending.warnings);
  a.querySelector('.reset').onclick = () => { ed.value = ln.zh; ed.focus(); };
  a.querySelector('.save').onclick = async () => {
    msg.textContent = '保存中…';
    try {
      const r = await fetch('/api/edit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: ln.id, zh: ed.value, note: note.value }),
      });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error || r.statusText);
      msg.textContent = `已存草稿（共 ${b.pending_total} 条待清关）`;
      renderWarnings(warn, b.warnings);
      // 就地刷新该行，让右栏立刻显示改后的样子
      const row = a.previousElementSibling;
      ln.pending = { zh: b.record.zh, note: b.record.note, ts: b.record.ts,
                     base_zh: b.record.base_zh, stale: false, warnings: b.warnings };
      const fresh = rowNode(ln);
      row.replaceWith(fresh);
      fresh.after(a);
      S.pendingCount = b.pending_total;
      updateStat();
    } catch (e) {
      msg.textContent = `失败：${e.message}`;
    }
  };
}

function updateStat() {
  const el = $('#pendstat');
  if (!el) return;
  el.textContent = S.pendingCount ? `✎ ${S.pendingCount} 条待清关` : '';
  el.style.display = S.pendingCount ? '' : 'none';
}

// ---- 流式装载 ----

async function loadUnit(seq, { replace = false } = {}) {
  if (S.busy) return;
  S.busy = true;
  try {
    if (!S.units[seq]) S.units[seq] = await getJSON(`/api/unit?seq=${seq}`);
    const u = S.units[seq];
    const stream = $('#stream');
    if (replace) { stream.innerHTML = ''; S.loaded = []; }
    stream.appendChild(unitNode(u));
    S.loaded.push(seq);
    S.cur = seq;
    markOutline(seq);
    $('#more').textContent = u.next_seq == null ? '—— 全书到此为止 ——' : '继续往下滚以载入下一单元…';
  } catch (e) {
    $('#more').textContent = `载入失败：${e.message}`;
  } finally {
    S.busy = false;
  }
}

function jumpTo(seq, hlId) {
  loadUnit(seq, { replace: true }).then(() => {
    $('#main').scrollTop = 0;
    if (hlId) {
      const r = document.querySelector(`.row[data-id="${hlId}"]`);
      if (r) { r.scrollIntoView({ block: 'center' }); r.style.outline = '2px solid var(--accent)'; }
    }
  });
}

async function loadNext() {
  const last = S.loaded[S.loaded.length - 1];
  const u = S.units[last];
  if (!u || u.next_seq == null) return;
  await loadUnit(u.next_seq);
}

// ---- 搜索 ----

let findTimer = null;
function onFind() {
  clearTimeout(findTimer);
  findTimer = setTimeout(async () => {
    const q = $('#find').value.trim();
    if (!q) { renderOutline(); $('#findinfo').textContent = ''; return; }
    if (/^\d+$/.test(q)) {
      try {
        const r = await getJSON(`/api/locate?id=${q}`);
        $('#findinfo').textContent = `id ${q} → 单元 #${r.seq}`;
        jumpTo(r.seq, Number(q));
      } catch (e) { $('#findinfo').textContent = e.message; }
      return;
    }
    const r = await getJSON(`/api/search?q=${encodeURIComponent(q)}`);
    $('#findinfo').textContent = `${r.hits.length} 条命中${r.truncated ? '（已截断，只显示前 200 条）' : ''}`;
    const box = $('#outline');
    box.innerHTML = '';
    for (const h of r.hits) {
      const d = document.createElement('div');
      d.className = 'hit';
      d.innerHTML = `<div class="mono" style="color:var(--faint);font-size:11px">${h.id} · #${h.seq} · ${esc(h.where)}</div>`
        + `<div class="hj">${esc(h.jp).slice(0, 60)}</div><div>${esc(h.zh).slice(0, 60)}</div>`;
      d.onclick = () => jumpTo(h.seq, h.id);
      box.appendChild(d);
    }
  }, 220);
}

// ---- 启动 ----

(async function init() {
  const o = await getJSON('/api/outline');
  S.outline = o.units;
  $('#lane').textContent = o.lane;
  const nUnit = o.units.filter((u) => u.type === 'unit').length;
  $('#stat').textContent = `${nUnit} 单元 · ${o.total_lines} 行 / ledger ${o.ledger_lines}`;
  renderOutline();
  await loadUnit(S.outline[0].seq, { replace: true });

  $('#main').addEventListener('scroll', () => {
    const el = $('#main');
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 400) loadNext();
    // 当前单元跟随滚动位置更新左栏高亮
    const secs = [...document.querySelectorAll('#stream > [data-seq]')];
    for (const s of secs) {
      if (s.offsetTop <= el.scrollTop + 120) S.cur = Number(s.dataset.seq);
    }
    markOutline(S.cur);
  }, { passive: true });

  const pend = await getJSON('/api/pending');
  S.pendingCount = pend.total;
  updateStat();

  $('#pendstat').onclick = async () => {
    const r = await getJSON('/api/pending');
    $('#findinfo').textContent = `${r.total} 条待清关 · 草稿 ${r.path}`;
    const box = $('#outline');
    box.innerHTML = '';
    for (const h of r.rows) {
      const d = document.createElement('div');
      d.className = 'hit';
      d.innerHTML = `<div class="mono" style="color:var(--faint);font-size:11px">`
        + `${h.id} · #${h.seq}${h.stale ? ' · ⚠ 已漂移' : ''}</div>`
        + `<div class="hj">${esc(h.base_zh).slice(0, 56)}</div>`
        + `<div>${esc(h.zh).slice(0, 56)}</div>`;
      d.onclick = () => jumpTo(h.seq, h.id);
      box.appendChild(d);
    }
  };

  $('#find').addEventListener('input', onFind);
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    const order = S.outline.map((u) => u.seq);
    const i = order.indexOf(S.cur);
    if (e.key === 'j' && i + 1 < order.length) jumpTo(order[i + 1]);
    else if (e.key === 'k' && i > 0) jumpTo(order[i - 1]);
    else if (e.key === '/') { e.preventDefault(); $('#find').focus(); }
    else if (e.key === 'n') {
      S.filtered = !S.filtered;
      $('#stream').classList.toggle('filtered', S.filtered);
      $('#more').textContent = S.filtered ? '（只显示有修订记录的行）' : '继续往下滚以载入下一单元…';
    }
  });
})();
