// Absolute Axis - Gig Platform Module（接案中樞）
// 案件名稱、需求、聯絡方式、拒絕理由、帳號名稱都是使用者輸入（未登入的訪客也能發案）：
// 一律用 h()／textContent 顯示（dom.js），按鈕用事件綁定，不組 HTML／onclick 字串。
let currentGigTab = 'active';
window.allGigsCache = [];

const _GIG_STATUS = {
    Open: ['info', '開放承接'], Assigned: ['warn', '進行中'], Completed: ['ok', '已完成'], Rejected: ['bad', '已拒絕'],
};

function _gigDetail(data, fallback) {
    return typeof (data && data.detail) === 'string' ? data.detail : fallback;
}

function _gigNote(text) {
    const container = document.getElementById('gigs-list-container');
    if (container) container.replaceChildren(h('p', { class: 'w-muted post-empty', text }));
}

async function loadGigs() {
    const container = document.getElementById('gigs-list-container');
    if (!container) return;
    const token = localStorage.getItem('axis_token');
    const gigsNav = document.getElementById('gigs-intro-navbar');
    if (gigsNav) gigsNav.style.display = !token ? 'flex' : 'none';
    const contactContainer = document.getElementById('gig-contact-container');
    if (contactContainer) contactContainer.style.display = !token ? 'block' : 'none';
    try {
        const res = await authFetch('/api/gigs');
        if (!res.ok) {
            _gigNote('無法取得案件清單');
            return;
        }
        window.allGigsCache = await res.json();
        renderGigsList();
    } catch (e) {
        console.error('Failed to load gigs:', e);
        _gigNote('載入案件時發生錯誤');
    }
}

function switchGigTab(tab) {
    currentGigTab = tab;
    const active = document.getElementById('tab-gig-active');
    const completed = document.getElementById('tab-gig-completed');
    if (active) active.setAttribute('aria-pressed', String(tab === 'active'));
    if (completed) completed.setAttribute('aria-pressed', String(tab === 'completed'));
    renderGigsList();
}
window.switchGigTab = switchGigTab;

function _gigButton(text, cls, onclick) {
    return h('button', { type: 'button', class: `btn ${cls} btn-sm`, text, onclick });
}

function renderGigsList() {
    const container = document.getElementById('gigs-list-container');
    if (!container || !window.allGigsCache) return;
    const gigs = window.allGigsCache.filter((g) => currentGigTab === 'completed'
        ? g.status === 'Completed'
        : g.status === 'Open' || g.status === 'Assigned');
    if (!gigs.length) {
        _gigNote(currentGigTab === 'completed' ? '目前沒有已完成的委託。' : '目前沒有進行中的委託。');
        return;
    }
    const token = localStorage.getItem('axis_token');
    const me = localStorage.getItem('axis_user');
    const isAdmin = localStorage.getItem('axis_role') === 'Administrator';

    container.replaceChildren(...gigs.map((g) => {
        const [tone, label] = _GIG_STATUS[g.status] || ['muted', g.status];
        const actions = h('div', { class: 'post-actions' });
        const workerNote = (suffix = '') => h('span', { class: 'post-meta', text: `承接人：${g.worker || '—'}${suffix}` });

        if (g.status === 'Open') {
            if (!token) {
                actions.append(_gigButton('登入以承接案件', 'btn-outline', () => showLoginOverlay()));
            } else {
                if (g.creator === me || isAdmin) {
                    actions.append(_gigButton(g.creator === me ? '撤回案件' : '刪除案件', 'btn-danger', () => deleteGig(g.id)));
                }
                if (g.creator !== me) {
                    actions.append(
                        _gigButton('承接委託', 'btn-primary', () => acceptGig(g.id)),
                        _gigButton('拒絕承接', 'btn-outline', () => rejectGigPrompt(g.id)));
                }
            }
        } else if (g.status === 'Assigned') {
            if (me === g.creator || me === g.worker || isAdmin) {
                actions.append(_gigButton('標記為已完成', 'btn-primary', () => completeGig(g.id)));
            }
            if (isAdmin) actions.append(_gigButton('刪除案件', 'btn-danger', () => deleteGig(g.id)));
            actions.append(workerNote());
        } else if (g.status === 'Completed') {
            if (isAdmin) actions.append(_gigButton('刪除案件', 'btn-danger', () => deleteGig(g.id)));
            actions.append(workerNote('（已驗收）'));
        }

        const creator = g.creator === 'Guest' && g.contact ? `訪客（聯絡：${g.contact}）` : g.creator;
        return h('article', { class: 'post-card' },
            h('div', { class: 'post-head' },
                h('h4', { class: 'post-title', text: g.title }),
                h('span', { class: `pill ${tone}`, text: label }),
                h('span', { class: 'post-budget', text: `NT$ ${Number(g.budget || 0).toLocaleString('zh-TW')}` })),
            h('p', { class: 'post-body', text: g.description }),
            g.status === 'Rejected' ? h('p', { class: 'post-warn', text: `拒絕原因：${g.reject_reason || '未提供理由'}` }) : null,
            h('div', { class: 'post-meta', text: `${creator} · ${shortTime(g.created_at)}` }),
            actions.childNodes.length ? actions : null);
    }));
}

async function submitGig() {
    const token = localStorage.getItem('axis_token');
    const title = document.getElementById('gig-title-input').value.trim();
    const description = document.getElementById('gig-desc-input').value.trim();
    const budget = parseInt(document.getElementById('gig-budget-input').value, 10);
    let contact = null;
    if (!token) {
        contact = document.getElementById('gig-contact-input').value.trim();
        if (!contact) {
            toastText('未登入的訪客請留下聯絡方式', 'error');
            return;
        }
    }
    if (!title || !description || isNaN(budget) || budget <= 0) {
        toastText('請填寫案件名稱、需求內容與有效的預算', 'error');
        return;
    }
    try {
        const res = await authFetch('/api/gigs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description, budget, contact })
        });
        if (res.ok) {
            toastText('案件已發佈', 'success');
            for (const id of ['gig-title-input', 'gig-desc-input', 'gig-budget-input', 'gig-contact-input']) {
                const el = document.getElementById(id);
                if (el) el.value = '';
            }
            loadGigs();
        } else {
            toastText(_gigDetail(await res.json().catch(() => null), '發佈失敗'), 'error');
        }
    } catch (err) {
        console.error(err);
        toastText('連線錯誤，請稍後再試', 'error');
    }
}

function _gigNeedLogin() {
    if (localStorage.getItem('axis_token')) return false;
    if (typeof showLoginOverlay === 'function') showLoginOverlay();
    return true;
}

async function _gigPost(url, body, okText) {
    try {
        const res = await authFetch(url, body === undefined ? { method: 'POST' } : {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        if (res.ok) {
            toastText(okText, 'success');
            loadGigs();
        } else {
            toastText(_gigDetail(await res.json().catch(() => null), '操作失敗'), 'error');
        }
    } catch (e) {
        console.error(e);
        toastText('連線錯誤，請稍後再試', 'error');
    }
}

async function acceptGig(id) {
    if (_gigNeedLogin()) return;
    await _gigPost(`/api/gigs/${encodeURIComponent(id)}/accept`, undefined, '已承接這個委託');
}

async function completeGig(id) {
    if (_gigNeedLogin()) return;
    if (!(await axisAsk({ title: '把這個案件標記為已完成？', message: '確認成果已交付並通過驗收。', ok: '標記完成' }))) return;
    await _gigPost(`/api/gigs/${encodeURIComponent(id)}/complete`, undefined, '案件已標記為完成');
}

async function deleteGig(id) {
    if (_gigNeedLogin()) return;
    if (!(await axisAsk({ title: '撤回／刪除這個案件？', message: '刪除後無法復原。', ok: '刪除', danger: true }))) return;
    try {
        const res = await authFetch(`/api/gigs/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (res.ok) {
            toastText('案件已刪除', 'success');
            loadGigs();
        } else {
            toastText(_gigDetail(await res.json().catch(() => null), '刪除失敗'), 'error');
        }
    } catch (e) {
        console.error(e);
        toastText('連線錯誤，請稍後再試', 'error');
    }
}

async function rejectGigPrompt(id) {
    if (_gigNeedLogin()) return;
    const reason = await axisAsk({ title: '拒絕承接這個案件', message: '請寫下原因，發案人會看到。', ok: '拒絕承接',
                                   danger: true, input: '', placeholder: '拒絕原因' });
    if (reason === null) return;
    if (!reason.trim()) {
        toastText('拒絕原因不能是空的', 'error');
        return;
    }
    await _gigPost(`/api/gigs/${encodeURIComponent(id)}/reject`, { reason: reason.trim() }, '已拒絕承接');
}

window.loadGigs = loadGigs;
window.submitGig = submitGig;
window.acceptGig = acceptGig;
window.completeGig = completeGig;
window.deleteGig = deleteGig;
window.rejectGigPrompt = rejectGigPrompt;
