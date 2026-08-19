/* P5 逐条裁决 UI。纯原生 DOM，无框架无 CDN（规格 §6）。
 *
 * 三条与需求直接对应、改动时别改坏的地方：
 * 1. `fillEditor()` —— 「填入编辑框」**仅当编辑框为空时生效**（规格 §4.3）。
 *    编辑框非空时按钮同时置灰 + 点了给提示，两道都留着：置灰防误触，提示解释原因。
 * 2. 编辑框内容一律**原样**发给服务端，前端不 trim、不校验、不替换任何字符
 *    （规格 §1.4：里面可能是给主控会话的批注而不是译文）。
 * 3. 左右两栏用同一份 `context` 行表渲染进同一个 CSS grid，逐行对齐靠 grid 行高，
 *    不要改成两个独立滚动区——那样同一 id 在左右就不再等高了。
 */
'use strict';

const S = {
  meta: null,
  items: [],
  byId: new Map(),
  filter: 'all',
  selected: null,
  item: null,
  editorCache: new Map(),   // id -> 编辑框草稿（切换条目不丢，防止手写内容被清掉）
};

const $ = (s) => document.querySelector(s);
const el = { qlist: null, pane: null, editor: null, reason: null, note: null };

/* ---------------- 基础工具 ---------------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* 控制码与 ruby 保持**字面**显示（不渲染成真 ruby）——裁决时要看到文件里到底
 * 写了什么，任何"美化渲染"都会让 `_n` 位置、注音拼写这类改动看不见。只上色。 */
function fmt(s) {
  return esc(s)
    .replace(/&lt;([^,&]+),([^&]+?)&gt;/g, '<span class="ruby">&lt;$1,$2&gt;</span>')
    .replace(/_n|_r/g, (m) => '<span class="ctl">' + m + '</span>');
}

/* 字符级 diff：先掐公共前后缀，剩余部分跑 LCS DP。纯视觉提示，不参与任何判定；
 * 剩余乘积过大时退化成"整段删+整段增"，宁可粗糙也不让界面卡住。 */
function diffChars(a, b) {
  a = a || ''; b = b || '';
  let p = 0;
  while (p < a.length && p < b.length && a[p] === b[p]) p++;
  let s = 0;
  while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++;
  const A = a.slice(p, a.length - s), B = b.slice(p, b.length - s);
  const out = [];
  if (p) out.push([0, a.slice(0, p)]);
  if (!A.length || !B.length || A.length * B.length > 200000) {
    if (A.length) out.push([-1, A]);
    if (B.length) out.push([1, B]);
  } else {
    const n = A.length, m = B.length;
    const dp = new Int32Array((n + 1) * (m + 1));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i * (m + 1) + j] = A[i] === B[j]
          ? dp[(i + 1) * (m + 1) + j + 1] + 1
          : Math.max(dp[(i + 1) * (m + 1) + j], dp[i * (m + 1) + j + 1]);
      }
    }
    let i = 0, j = 0;
    const push = (op, ch) => {
      if (out.length && out[out.length - 1][0] === op) out[out.length - 1][1] += ch;
      else out.push([op, ch]);
    };
    while (i < n && j < m) {
      if (A[i] === B[j]) { push(0, A[i]); i++; j++; }
      else if (dp[(i + 1) * (m + 1) + j] >= dp[i * (m + 1) + j + 1]) { push(-1, A[i]); i++; }
      else { push(1, B[j]); j++; }
    }
    while (i < n) { push(-1, A[i]); i++; }
    while (j < m) { push(1, B[j]); j++; }
  }
  if (s) out.push([0, a.slice(a.length - s)]);
  return out;
}

function renderDiff(cur, cand) {
  return diffChars(cur, cand).map(([op, t]) =>
    op === 0 ? fmt(t)
      : op === 1 ? '<span class="d-ins">' + fmt(t) + '</span>'
        : '<span class="d-del">' + fmt(t) + '</span>').join('');
}

let toastTimer = null;
function toast(msg) {
  let t = $('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.remove(), 2200);
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({ error: 'HTTP ' + r.status }));
  if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
  return data;
}

/* ---------------- 队列（左栏） ---------------- */
const VERDICT_BADGE = {
  adopt: ['b-adopt', '采'], adopt_alt: ['b-alt', '备'],
  edit: ['b-edit', '编'], keep: ['b-keep', '留'],
};

function isWarn(it) { return it.drift || it.soft || it.hard; }

function viewItems() {
  return S.items.filter((it) =>
    S.filter === 'all' ? true
      : S.filter === 'todo' ? !it.verdict
        : S.filter === 'done' ? !!it.verdict
          : isWarn(it));
}

function rowHtml(it) {
  const [cls, txt] = VERDICT_BADGE[it.verdict] || ['b-todo', '·'];
  let b = '<span class="badge ' + cls + '" title="' + (it.verdict || '未处理') + '">' + txt + '</span>';
  if (it.drift) b += ' <span class="badge b-drift" title="冻结后车道已更新">⚠</span>';
  if (it.hard) b += ' <span class="badge b-lock" title="硬锁">硬</span>';
  else if (it.soft) b += ' <span class="badge b-lock" title="软锁（锚点行）">锁</span>';
  return '<div class="qrow' + (it.id === S.selected ? ' sel' : '') + '" data-id="' + it.id + '">'
    + '<span class="qid">' + it.id + '</span>'
    + '<span class="qb">b' + it.batch + '</span>'
    + '<span class="qn" title="有提案的通道数 / 出过候选的通道数">'
    + it.n_proposals + '/' + it.n_covered + '</span>'
    + '<span class="qgrow"></span>' + b + '</div>';
}

function renderQueue() {
  el.qlist.innerHTML = viewItems().map(rowHtml).join('');
  const done = S.items.filter((it) => it.verdict).length;
  $('#progress').textContent = '已处理 ' + done + ' / ' + S.items.length
    + '（本视图 ' + viewItems().length + '）';
}

function markSelected() {
  el.qlist.querySelectorAll('.qrow.sel').forEach((n) => n.classList.remove('sel'));
  const n = el.qlist.querySelector('.qrow[data-id="' + S.selected + '"]');
  if (n) { n.classList.add('sel'); n.scrollIntoView({ block: 'nearest' }); }
}

/* ---------------- 对读区（右主体） ---------------- */
function propHtml(p, cur, idx) {
  const tags = [];
  if (p.adjudicate) tags.push('<span class="tag req">请裁</span>');
  if (p.same_as_current) tags.push('<span class="tag same">与现行译文逐字相同</span>');
  else if (p.same_as_frozen) tags.push('<span class="tag same">＝冻结面（提案实为回退到冻结面）</span>');
  const btn = (label, act, extra, text) =>
    '<button data-act="' + act + '" data-ch="' + esc(p.channel) + '"' + extra
    + ' data-text="' + esc(text) + '">' + label + '</button>';
  let h = '<div class="prop' + (p.adjudicate ? ' adj' : '') + '" data-i="' + idx + '">'
    + '<div class="prop-head"><span class="ch">' + esc(p.channel) + '</span>'
    + '<span>score ' + (p.score == null ? '-' : p.score) + '</span>' + tags.join(' ') + '</div>'
    + '<div class="prop-zh">' + renderDiff(cur, p.zh) + '</div>'
    + (p.note ? '<div class="prop-note">' + fmt(p.note) + '</div>' : '')
    + '<div class="btns">' + btn('采纳', 'adopt', '', p.zh)
    + btn('填入编辑框', 'fill', ' class="btn-fill"', p.zh) + '</div>';
  (p.alts || []).forEach((a, k) => {
    h += '<div class="alt"><div class="alt-lbl">备选' + (k + 1) + '</div>'
      + '<div class="prop-zh">' + renderDiff(cur, a.zh) + '</div>'
      + (a.note ? '<div class="prop-note">' + fmt(a.note) + '</div>' : '')
      + '<div class="btns">'
      + btn('采纳备选' + (k + 1), 'adopt_alt', ' data-alt="' + (k + 1) + '"', a.zh)
      + btn('填入编辑框', 'fill', ' class="btn-fill"', a.zh) + '</div></div>';
  });
  return h + '</div>';
}

function renderItem(it) {
  const parts = [];
  parts.push('<div class="itemhead"><h2>id ' + it.id + '</h2>'
    + '<span class="meta">批 ' + it.batch + '　队列第 ' + (it.queue_index + 1)
    + ' / ' + it.queue_total + '　提案通道：'
    + esc(it.proposals.map((p) => p.channel).join('、') || '无') + '</span></div>');
  parts.push('<div class="colhead"><div>日文原文（frozen/source）</div>'
    + '<div>最新落盘译文（车道 resolve：patches ∥ forward）</div></div>');
  parts.push('<div class="lines">');

  for (const r of it.context) {
    if (r.current) {
      const warn = it.drift ? ' <span class="badge b-drift" title="冻结后车道已更新">⚠</span>' : '';
      parts.push('<div class="cell jp cur"><span class="rowid">' + r.id + '</span>' + fmt(r.jp) + '</div>');
      parts.push('<div class="cell zh cur">' + fmt(r.zh) + warn + '</div>');
      // 提案块 = grid 第 2 列的一个独立行 → 正好落在右栏当前行的正下方
      const props = [];
      if (it.drift) {
        props.push('<div class="drift"><b>⚠ 冻结后车道已更新</b>'
          + '（判据：' + esc(it.drift.source) + '）——下面各通道的候选是对着<b>冻结面</b>产出的，'
          + '采纳前先确认不是把冻结后的修正回退掉。'
          + '<span class="t"><span class="lbl">冻结面</span>' + fmt(it.drift.frozen) + '</span>'
          + '<span class="t"><span class="lbl">车道最新</span>' + fmt(it.drift.current) + '</span></div>');
      }
      if (it.hard || it.soft) {
        props.push('<div class="lockbar"><b>' + (it.hard ? '硬锁' : '软锁（锚点行）') + '</b>'
          + (it.lock_why ? '：' + fmt(it.lock_why) : '') + '</div>');
      }
      const shown = it.proposals.filter((p) => !p.collapsible);
      const hidden = it.proposals.filter((p) => p.collapsible);
      shown.forEach((p, i) => props.push(propHtml(p, it.zh_current, i)));
      if (hidden.length) {
        props.push('<div class="collapsed">另有 ' + hidden.length + ' 个通道与现行译文逐字相同且无批注（'
          + esc(hidden.map((p) => p.channel).join('、')) + '）</div>');
      }
      parts.push('<div class="props">' + props.join('') + '</div>');
    } else {
      const cls = r.verdict ? ' done' : (r.in_queue ? ' inq' : '');
      parts.push('<div class="cell jp ctxdim' + cls + '"><span class="rowid">' + r.id + '</span>' + fmt(r.jp) + '</div>');
      parts.push('<div class="cell zh ctxdim' + cls + '">' + fmt(r.zh) + '</div>');
    }
  }
  parts.push('</div>');
  el.pane.innerHTML = parts.join('');

  const cur = el.pane.querySelector('.cell.cur');
  if (cur) $('#main').scrollTop = Math.max(0, cur.offsetTop - $('#main').clientHeight * 0.32);

  const d = it.decision;
  $('#decision-state').innerHTML = d
    ? '当前草稿：<span class="now">' + esc(d.verdict)
    + (d.chosen_channel ? '（' + esc(d.chosen_channel)
      + (d.chosen_alt ? ' 备选' + d.chosen_alt : '') + '）' : '')
    + '</span>　' + esc(d.ts) + '　——可直接改判（追加新行）'
    : '未处理';
}

/* ---------------- 选择与动作 ---------------- */
async function selectItem(id) {
  if (id == null) { toast('没有下一条了'); return; }
  if (S.selected != null) S.editorCache.set(S.selected, el.editor.value);
  S.selected = id;
  markSelected();
  el.editor.value = S.editorCache.get(id) || '';
  syncFillButtons();
  try {
    S.item = await api('/api/item?id=' + id);
  } catch (e) { el.pane.textContent = '载入失败：' + e.message; return; }
  renderItem(S.item);
  syncFillButtons();
}

function nextTarget(fromId, onlyUndecided) {
  const view = viewItems();
  if (!view.length) return null;
  const idx = view.findIndex((x) => x.id === fromId);
  for (let k = 1; k <= view.length; k++) {
    const it = view[(idx + k + view.length) % view.length];
    if (!onlyUndecided || !it.verdict) return it.id;
  }
  return null;
}

async function decide(payload) {
  if (S.selected == null) return;
  payload.id = S.selected;
  payload.reason_code = el.reason.value;   // reason 刻意跨条目保留：连续裁决常是同一类问题
  payload.note = el.note.value;
  let res;
  try {
    res = await api('/api/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (e) { toast('写草稿失败：' + e.message); return; }
  const it = S.byId.get(S.selected);
  if (it) { it.verdict = res.record.verdict; it.chosen_channel = res.record.chosen_channel; }
  S.editorCache.delete(S.selected);
  el.editor.value = '';
  el.note.value = '';
  const nxt = nextTarget(S.selected, true);
  renderQueue();
  await selectItem(nxt != null ? nxt : res.next_undecided);
}

function fillEditor(text) {
  // 规格 §4.3：仅当编辑框为空时生效。这里用 `!== ''` 而不是 trim——用户可能
  // 故意只敲了空白/换行占位，那也算"写了一半"，不该被覆盖。
  if (el.editor.value !== '') { toast('编辑框非空，未填入（先清空再点）'); return; }
  el.editor.value = text;
  syncFillButtons();
  el.editor.focus();
}

function syncFillButtons() {
  const dis = el.editor.value !== '';
  el.pane.querySelectorAll('.btn-fill').forEach((b) => {
    b.disabled = dis;
    b.title = dis ? '编辑框非空时不填入（防误触覆盖）' : '把这条文本填进编辑框';
  });
}

/* ---------------- 事件绑定 ---------------- */
function bind() {
  el.qlist.addEventListener('click', (e) => {
    const row = e.target.closest('.qrow');
    if (row) selectItem(Number(row.dataset.id));
  });

  el.pane.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    const act = b.dataset.act;
    if (act === 'fill') fillEditor(b.dataset.text);
    else if (act === 'adopt') decide({ verdict: 'adopt', chosen_channel: b.dataset.ch });
    else if (act === 'adopt_alt') {
      decide({ verdict: 'adopt_alt', chosen_channel: b.dataset.ch, chosen_alt: Number(b.dataset.alt) });
    }
  });

  $('#btn-keep').addEventListener('click', () => decide({ verdict: 'keep' }));
  $('#btn-edit').addEventListener('click', () => {
    if (el.editor.value === '') { toast('编辑框是空的'); return; }
    decide({ verdict: 'edit', edited_zh: el.editor.value });   // 原样，不 trim
  });
  $('#btn-skip').addEventListener('click', () => {
    const nxt = nextTarget(S.selected, false);
    if (nxt != null) selectItem(nxt); else toast('没有下一条了');
  });

  el.editor.addEventListener('input', syncFillButtons);
  el.editor.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('#btn-edit').click(); }
  });

  document.querySelectorAll('.filter').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.filter').forEach((x) => x.classList.toggle('on', x === b));
    S.filter = b.dataset.filter;
    renderQueue();
    markSelected();
  }));

  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'textarea' || tag === 'input') return;
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const view = viewItems();
    if (!view.length) return;
    const idx = view.findIndex((x) => x.id === S.selected);
    const nx = view[Math.min(view.length - 1, Math.max(0, idx + (e.key === 'ArrowDown' ? 1 : -1)))];
    if (nx) selectItem(nx.id);
  });
}

async function boot() {
  el.qlist = $('#qlist'); el.pane = $('#pane'); el.editor = $('#editor');
  el.reason = $('#reason'); el.note = $('#note');
  bind();
  let q;
  try { q = await api('/api/queue'); } catch (e) { el.pane.textContent = '载入队列失败：' + e.message; return; }
  S.meta = q;
  S.items = q.items;
  S.byId = new Map(q.items.map((it) => [it.id, it]));
  $('#seg').textContent = q.seg + '　通道 ' + q.channels.join('、');
  $('#draft-path').textContent = q.draft_path;
  renderQueue();
  const first = S.items.find((it) => !it.verdict) || S.items[0];
  if (first) selectItem(first.id);
}

boot();
