// Absolute Axis - Open Source Repos Module（開源分享）
// 專案名稱、描述、連結來自 GitHub 或管理員輸入：一律用 h()／textContent 顯示（dom.js），
// 連結只接受 http(s)，按鈕用事件綁定；刪除用頁內確認（axisAsk），不用 confirm()。

const _OS_LANG_COLOR = {
    Python: '#3572A5', JavaScript: '#F1E05A', TypeScript: '#3178C6', HTML: '#E34C26',
    CSS: '#563D7C', Shell: '#89E051', 'C++': '#F34B7D', C: '#555555', Go: '#00ADD8', Java: '#B07219',
};

function _osSafeUrl(url) {
    try {
        const u = new URL(String(url || ''), location.origin);
        return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
    } catch (e) {
        return null;
    }
}

function _osDetail(data, fallback) {
    return typeof (data && data.detail) === 'string' ? data.detail : fallback;
}

async function loadGitHubRepos() {
    const grid = document.getElementById('repos-grid');
    if (!grid) return;
    const role = localStorage.getItem('axis_role');
    const isAdmin = role === 'admin' || role === 'Administrator';
    const addBtn = document.getElementById('os-add-repo-btn');
    if (addBtn) addBtn.style.display = isAdmin ? '' : 'none';

    try {
        const configRes = await authFetch('/api/github/config');
        if (configRes.ok) {
            const config = await configRes.json();
            const subtitle = document.getElementById('os-subtitle');
            const authorUrl = document.getElementById('os-author-url');
            if (subtitle && config.developer_name) {
                subtitle.textContent = `自動同步 ${config.developer_name} 在 GitHub 上的公開專案與開源成果`;
            }
            const href = _osSafeUrl(config.github_url);
            if (authorUrl && href) authorUrl.href = href;
        }
    } catch (e) {
        console.error('Failed to load github config in view:', e);
    }

    const note = (text) => grid.replaceChildren(h('p', { class: 'w-muted post-empty', text }));
    try {
        const res = await authFetch('/api/github/repos');
        if (!res.ok) {
            note('無法取得開源專案');
            return;
        }
        const repos = await res.json();
        if (!repos.length) {
            note('還沒有任何公開專案。');
            return;
        }
        grid.replaceChildren(...repos.map((repo) => _osCard(repo, isAdmin)));
    } catch (e) {
        console.error('Failed to load repos:', e);
        note('載入開源專案時發生錯誤');
    }
}

function _osCard(repo, isAdmin) {
    const lang = repo.language || '其他';
    const href = _osSafeUrl(repo.html_url);
    const clone = href ? `git clone ${href.replace(/\/$/, '')}.git` : '';
    const footer = h('div', { class: 'repo-foot' },
        h('span', { class: 'repo-lang' },
            h('i', { style: `background:${_OS_LANG_COLOR[lang] || 'var(--text-muted)'}` }), lang),
        h('span', { class: 'repo-actions' },
            isAdmin ? h('button', { type: 'button', class: 'btn btn-danger btn-sm', text: '刪除',
                                    onclick: () => window.deleteRepo(repo.name) }) : null,
            href ? h('a', { class: 'btn btn-outline btn-sm', href, target: '_blank', rel: 'noopener noreferrer',
                            text: '查看原始碼' }) : null));
    return h('article', { class: 'repo-card' },
        h('div', { class: 'repo-head' },
            h('span', { class: 'nav-ico', style: 'background:#4A4A54' },
                _osIcon()),
            h('h4', { class: 'repo-name', text: repo.name }),
            h('span', { class: 'repo-stats', text: `★ ${repo.stars ?? 0}  ⑂ ${repo.forks ?? 0}` })),
        h('p', { class: 'repo-desc', text: repo.description || '沒有專案描述。' }),
        clone ? h('div', { class: 'repo-clone' },
            h('code', { text: clone }),
            h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: '複製',
                          onclick: () => window.copyCloneCommand(clone) })) : null,
        footer);
}

function _osIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', 'M8 8l-4 4 4 4M16 8l4 4-4 4');
    svg.append(p);
    return svg;
}

window.copyCloneCommand = async function (text) {
    try {
        await navigator.clipboard.writeText(text);
        toastText('已複製 git clone 指令', 'success');
    } catch (e) {
        toastText('無法使用剪貼簿，請手動選取指令複製', 'info');
    }
};

const _OS_FIELDS = ['os-import-url', 'os-repo-name', 'os-repo-fullname', 'os-repo-url', 'os-repo-lang', 'os-repo-desc'];

window.showAddRepoModal = function () {
    const modal = document.getElementById('os-add-repo-modal');
    if (!modal) return;
    for (const id of _OS_FIELDS) document.getElementById(id).value = '';
    const btn = document.getElementById('os-import-btn');
    if (btn) { btn.disabled = false; btn.textContent = '解析'; }
    modal.style.display = 'flex';
    document.getElementById('os-import-url').focus();
};

window.hideAddRepoModal = function () {
    const modal = document.getElementById('os-add-repo-modal');
    if (modal) modal.style.display = 'none';
};

function _osFill(data) {
    document.getElementById('os-repo-name').value = data.name || '';
    document.getElementById('os-repo-fullname').value = data.full_name || '';
    document.getElementById('os-repo-url').value = data.html_url || '';
    document.getElementById('os-repo-lang').value = data.language || '';
    document.getElementById('os-repo-desc').value = data.description || '';
}

async function _osParse(url) {
    const btn = document.getElementById('os-import-btn');
    if (btn) { btn.disabled = true; btn.textContent = '解析中…'; }
    try {
        const res = await authFetch('/api/github/parse-url?url=' + encodeURIComponent(url));
        const data = await res.json().catch(() => null);
        if (res.ok && data) {
            _osFill(data);
            return true;
        }
        toastText(_osDetail(data, '解析專案連結失敗'), 'error');
        return false;
    } catch (e) {
        toastText('連線錯誤，請稍後再試', 'error');
        return false;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '解析'; }
    }
}

window.importFromUrl = async function () {
    const url = document.getElementById('os-import-url').value.trim();
    if (!url) {
        toastText('請貼上 GitHub 專案連結', 'error');
        return;
    }
    if (await _osParse(url)) toastText('已自動填入專案資訊', 'success');
};

window.submitAddRepo = async function () {
    const val = (id) => document.getElementById(id).value.trim();
    const importUrl = val('os-import-url');
    // 主要欄位空白但有貼連結：先自動解析一次
    if ((!val('os-repo-name') || !val('os-repo-fullname') || !val('os-repo-url')) && importUrl) {
        if (!(await _osParse(importUrl))) return;
    }
    const name = val('os-repo-name');
    const fullName = val('os-repo-fullname');
    const url = val('os-repo-url');
    if (!name || !fullName || !url) {
        toastText('請填寫名稱、完整名稱與連結', 'error');
        return;
    }
    if (!_osSafeUrl(url)) {
        toastText('連結必須以 https:// 開頭', 'error');
        return;
    }
    try {
        const res = await authFetch('/api/github/repos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name, full_name: fullName, html_url: url,
                language: val('os-repo-lang') || 'JavaScript', description: val('os-repo-desc'),
            })
        });
        if (res.ok) {
            toastText('已新增開源專案', 'success');
            window.hideAddRepoModal();
            await loadGitHubRepos();
        } else {
            toastText(_osDetail(await res.json().catch(() => null), '新增專案失敗'), 'error');
        }
    } catch (e) {
        toastText('連線錯誤，請稍後再試', 'error');
    }
};

window.deleteRepo = async function (name) {
    if (!(await axisAsk({ title: `刪除開源專案「${name}」？`, message: '只會從這個頁面移除，不會刪除 GitHub 上的專案。', ok: '刪除', danger: true }))) return;
    try {
        const res = await authFetch(`/api/github/repos/${encodeURIComponent(name)}`, { method: 'DELETE' });
        if (res.ok) {
            toastText('已刪除這個開源專案', 'success');
            await loadGitHubRepos();
        } else {
            toastText(_osDetail(await res.json().catch(() => null), '刪除專案失敗'), 'error');
        }
    } catch (e) {
        toastText('連線錯誤，請稍後再試', 'error');
    }
};

window.loadGitHubRepos = loadGitHubRepos;
