// Absolute Axis - 專案目標追蹤（每週目標／每日目標／Claude 每日進度同步）
// 專案名稱、路徑、目標文字、進度摘要都是使用者或排程任務寫入的內容：一律用 h()／textContent 顯示（dom.js），不插入 HTML。
// API：app/routers/goals.py（/api/goals，僅管理員）

window.goalsData = { projects: [], last_sync: null };
let _goalsWeekOffset = 0;   // 0 = 本週，1 = 下週，-1 = 上週
let _goalsTab = 'active';
const _GOALS_WD = ['日', '一', '二', '三', '四', '五', '六'];
const _GOALS_STATUS = { active: '開發中', paused: '暫停', done: '已完成' };

// ----------------- 日期 -----------------
function _goalsDateStr(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ISO 8601 週次，例如 2026-W48（與後端、goals_sync.py 的 isocalendar() 一致）
function _goalsWeekKey(d) {
    const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const dayNum = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    const week = Math.ceil(((t - yearStart) / 86400000 + 1) / 7);
    return `${t.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function _goalsWeekDays(offset) {
    const now = new Date();
    const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (now.getDay() || 7) + 1 + offset * 7);
    return [...Array(7)].map((_, i) => new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + i));
}

function _goalsWeekLabel(off) {
    if (off === 0) return '本週';
    if (off === 1) return '下週';
    if (off === -1) return '上週';
    return off > 0 ? `${off} 週後` : `${-off} 週前`;
}

// ----------------- API -----------------
async function _goalsApi(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const r = await authFetch(url, opts);
    let data = null;
    try { data = await r.json(); } catch (_) { /* 沒有內容 */ }
    if (!r.ok) {
        const msg = typeof (data && data.detail) === 'string' ? data.detail : `操作失敗（${r.status}）`;
        if (r.status < 500 && r.status !== 403) toastText(msg, 'error');  // 403／5xx authFetch 已提示
        throw new Error(msg);
    }
    return data;
}

async function loadGoals() {
    const box = document.getElementById('goals-projects');
    if (!box) return;
    try {
        window.goalsData = await _goalsApi('GET', '/api/goals');
        renderGoals();
    } catch (e) {
        box.replaceChildren(h('p', { class: 'w-muted post-empty', text: '無法取得專案目標（需要管理員權限）' }));
    }
}

// ----------------- 頁面操作 -----------------
function goalsShiftWeek(delta) { _goalsWeekOffset += delta; renderGoals(); }
function goalsJumpWeek(off) { _goalsWeekOffset = off; renderGoals(); }

function goalsSwitchTab(tab) {
    _goalsTab = tab;
    for (const t of Object.keys(_GOALS_STATUS)) {
        const b = document.getElementById('goals-tab-' + t);
        if (b) b.setAttribute('aria-pressed', String(t === tab));
    }
    renderGoals();
}

function goalsToggleAddProject(show) {
    const f = document.getElementById('goals-add-project');
    if (!f) return;
    f.hidden = !show;
    if (show) document.getElementById('goals-new-name').focus();
}

async function goalsCreateProject() {
    const name = document.getElementById('goals-new-name').value.trim();
    const path = document.getElementById('goals-new-path').value.trim();
    const description = document.getElementById('goals-new-desc').value.trim();
    if (!name) {
        toastText('請輸入專案名稱', 'error');
        return;
    }
    try {
        await _goalsApi('POST', '/api/goals/projects', { name, path, description });
        for (const id of ['goals-new-name', 'goals-new-path', 'goals-new-desc']) document.getElementById(id).value = '';
        goalsToggleAddProject(false);
        toastText(`已新增專案「${name}」`, 'success');
        await loadGoals();
    } catch (_) { /* 已提示 */ }
}

async function _goalsAdd(pid, kind, key, input) {
    const text = input.value.trim();
    if (!text) return;
    try {
        await _goalsApi('POST', `/api/goals/projects/${pid}/goals`, { kind, key, text });
        input.value = '';
        await loadGoals();
        // 重繪後把焦點放回同一個輸入框，方便連續輸入
        const again = document.querySelector(`input[data-goal-input="${pid}|${kind}|${key}"]`);
        if (again) again.focus();
    } catch (_) { /* 已提示 */ }
}

async function _goalsToggle(pid, gid, done) {
    try { await _goalsApi('PATCH', `/api/goals/projects/${pid}/goals/${gid}`, { done }); } catch (_) { /* 已提示 */ }
    loadGoals();
}

async function _goalsEdit(pid, g) {
    const text = await axisAsk({ title: '修改目標', ok: '儲存', input: g.text });
    if (text === null || !text.trim() || text.trim() === g.text) return;
    try { await _goalsApi('PATCH', `/api/goals/projects/${pid}/goals/${g.id}`, { text: text.trim() }); loadGoals(); } catch (_) { /* 已提示 */ }
}

async function _goalsDelete(pid, g) {
    try { await _goalsApi('DELETE', `/api/goals/projects/${pid}/goals/${g.id}`); loadGoals(); } catch (_) { /* 已提示 */ }
}

async function _goalsSetStatus(pid, status) {
    try { await _goalsApi('PUT', `/api/goals/projects/${pid}`, { status }); loadGoals(); } catch (_) { /* 已提示 */ }
}

async function _goalsEditProject(p) {
    const path = await axisAsk({ title: `「${p.name}」的本機路徑`, message: '排程任務用這個資料夾讀取 git 紀錄。', ok: '下一步', input: p.path || '', placeholder: 'E:\\...' });
    if (path === null) return;
    const description = await axisAsk({ title: '專案說明', ok: '儲存', input: p.description || '', placeholder: '一句話描述（選填）' });
    if (description === null) return;
    try {
        await _goalsApi('PUT', `/api/goals/projects/${p.id}`, { path: path.trim(), description: description.trim() });
        loadGoals();
    } catch (_) { /* 已提示 */ }
}

async function _goalsDeleteProject(p) {
    const ok = await axisAsk({ title: `刪除「${p.name}」？`, message: '這個專案的所有目標與進度紀錄都會一起刪除，無法復原。', ok: '刪除', danger: true });
    if (!ok) return;
    try {
        await _goalsApi('DELETE', `/api/goals/projects/${p.id}`);
        toastText('已刪除專案', 'success');
        loadGoals();
    } catch (_) { /* 已提示 */ }
}

// ----------------- 畫面 -----------------
function _goalsItem(pid, g) {
    const byClaude = g.done && g.done_by === 'claude-sync';
    const box = h('input', { type: 'checkbox', 'aria-label': g.text, onchange: (e) => _goalsToggle(pid, g.id, e.target.checked) });
    box.checked = !!g.done;
    return h('li', { class: 'goals-item' + (g.done ? ' is-done' : '') },
        box,
        h('span', { class: 'goals-text', text: g.text, title: '雙擊修改', ondblclick: () => _goalsEdit(pid, g) }),
        byClaude ? h('span', { class: 'pill info goals-auto', text: '自動', title: g.note || '由每日同步依進度自動勾選' }) : null,
        h('button', { type: 'button', class: 'goals-x', 'aria-label': '刪除目標', text: '×', onclick: () => _goalsDelete(pid, g) }));
}

function _goalsAddRow(pid, kind, key, placeholder) {
    const input = h('input', { type: 'text', maxlength: '300', placeholder, 'aria-label': placeholder, dataset: { goalInput: `${pid}|${kind}|${key}` } });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) _goalsAdd(pid, kind, key, input); });
    return h('div', { class: 'goals-add-row' }, input,
        h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: '加入', onclick: () => _goalsAdd(pid, kind, key, input) }));
}

function _goalsSection(title, extra) {
    return h('div', { class: 'goals-sec' }, h('span', { class: 'goals-sec-title', text: title }), extra || null);
}

function _goalsCard(p, weekKey, weekLabel, days, todayStr) {
    const weekly = (p.weekly_goals || {})[weekKey] || [];
    const wDone = weekly.filter((g) => g.done).length;
    const pct = weekly.length ? Math.round((wDone / weekly.length) * 100) : 0;

    // 每日目標：今天在這週內就展開今天，否則展開週一
    const daily = p.daily_goals || {};
    const inWeek = days.some((d) => _goalsDateStr(d) === todayStr);
    const dayBlocks = days.map((d) => {
        const ds = _goalsDateStr(d);
        const list = daily[ds] || [];
        const done = list.filter((g) => g.done).length;
        const isToday = ds === todayStr;
        const det = h('details', { class: 'goals-day' + (isToday ? ' is-today' : '') },
            h('summary', {},
                h('span', { text: `${isToday ? '今天 · ' : ''}週${_GOALS_WD[d.getDay()]} ${ds.slice(5)}` }),
                h('span', { class: 'w-muted goals-count', text: list.length ? `${done}/${list.length}` : '' })),
            h('ul', { class: 'goals-list' }, list.map((g) => _goalsItem(p.id, g))),
            _goalsAddRow(p.id, 'daily', ds, '新增當日目標，Enter 加入'));
        det.open = isToday || (!inWeek && d.getDay() === 1);
        return det;
    });

    const logs = p.progress_log || [];
    const logRow = (l) => h('div', { class: 'goals-log' },
        h('div', { class: 'goals-log-meta' },
            h('strong', { text: l.date }),
            h('span', { class: 'w-muted', text: [l.commits ? `${l.commits} commits` : '', l.files_changed ? `${l.files_changed} 個檔案異動` : ''].filter(Boolean).join(' · ') })),
        h('p', { class: 'goals-log-body', text: l.summary }));
    const history = h('div', { class: 'goals-history', hidden: true }, logs.slice(1, 14).map(logRow));
    const historyBtn = logs.length > 1
        ? h('button', { type: 'button', class: 'goals-link', text: `歷史（${logs.length - 1}）`, onclick: () => { history.hidden = !history.hidden; } })
        : null;

    const status = p.status || 'active';
    const statusBtns = Object.keys(_GOALS_STATUS).filter((s) => s !== status).map((s) =>
        h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: { active: '設為開發中', paused: '暫停', done: '標記完成' }[s], onclick: () => _goalsSetStatus(p.id, s) }));

    return h('article', { class: 'post-card goals-card' },
        h('div', { class: 'post-head' },
            h('h4', { class: 'post-title', text: p.name }),
            h('span', { class: `pill ${status === 'active' ? 'ok' : status === 'paused' ? 'warn' : ''}`, text: _GOALS_STATUS[status] })),
        p.description ? h('p', { class: 'post-meta', text: p.description }) : null,
        h('p', { class: 'goals-path' + (p.path ? '' : ' is-missing'), text: p.path || '未設定路徑：排程任務無法讀取這個專案的進度' }),

        _goalsSection(`${weekLabel}目標`, h('span', { class: 'w-muted goals-count', text: weekly.length ? `${wDone}/${weekly.length} · ${pct}%` : '' })),
        h('div', { class: 'progress-bar goals-bar' }, h('div', { class: 'progress-fill', style: `width:${pct}%` })),
        h('ul', { class: 'goals-list' }, weekly.length ? weekly.map((g) => _goalsItem(p.id, g)) : h('li', { class: 'w-muted goals-empty', text: '還沒有設定目標' })),
        _goalsAddRow(p.id, 'weekly', weekKey, `新增${weekLabel}目標，Enter 加入`),

        _goalsSection('每日目標'),
        h('div', { class: 'goals-days' }, dayBlocks),

        _goalsSection('最新進度', historyBtn),
        logs.length ? logRow(logs[0]) : h('p', { class: 'w-muted goals-empty', text: '尚無進度紀錄（等待每晚同步）' }),
        history,

        h('div', { class: 'post-actions' },
            h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: '編輯', onclick: () => _goalsEditProject(p) }),
            ...statusBtns,
            h('button', { type: 'button', class: 'btn btn-outline btn-sm goals-danger', text: '刪除', onclick: () => _goalsDeleteProject(p) })));
}

function renderGoals() {
    const box = document.getElementById('goals-projects');
    if (!box) return;

    const days = _goalsWeekDays(_goalsWeekOffset);
    const weekKey = _goalsWeekKey(days[0]);
    const weekLabel = _goalsWeekLabel(_goalsWeekOffset);
    const todayStr = _goalsDateStr(new Date());
    document.getElementById('goals-week-label').textContent = `${weekLabel} · ${weekKey}`;
    document.getElementById('goals-week-range').textContent = `${_goalsDateStr(days[0]).slice(5)} – ${_goalsDateStr(days[6]).slice(5)}`;
    for (const off of [0, 1]) {
        const b = document.getElementById('goals-wk-' + off);
        if (b) b.setAttribute('aria-pressed', String(_goalsWeekOffset === off));
    }

    const sync = window.goalsData.last_sync;
    document.getElementById('goals-sync-status').textContent = sync ? `上次同步 ${shortTime(sync.at)}` : '尚未同步';

    const projects = (window.goalsData.projects || []).filter((p) => (p.status || 'active') === _goalsTab);
    if (!projects.length) {
        box.replaceChildren(h('p', { class: 'w-muted post-empty goals-none',
            text: _goalsTab === 'active' ? '還沒有開發中的專案。按「新增專案」開始追蹤。' : '這個分類目前沒有專案。' }));
        return;
    }
    box.replaceChildren(...projects.map((p) => _goalsCard(p, weekKey, weekLabel, days, todayStr)));
}

window.loadGoals = loadGoals;
window.goalsShiftWeek = goalsShiftWeek;
window.goalsJumpWeek = goalsJumpWeek;
window.goalsSwitchTab = goalsSwitchTab;
window.goalsToggleAddProject = goalsToggleAddProject;
window.goalsCreateProject = goalsCreateProject;
