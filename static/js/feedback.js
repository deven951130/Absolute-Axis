// Absolute Axis - Feedback Hub Module（問題反饋）
// 反饋的標題、內容、提交者、管理員回覆都是使用者輸入：一律用 h()／textContent 顯示（dom.js），不插入 HTML。

const _FB_CATEGORY = { Bug: '系統錯誤', Suggestion: '功能建議', Other: '其他' };

function _fbDetail(data, fallback) {
    return typeof (data && data.detail) === 'string' ? data.detail : fallback;
}

async function loadFeedbacks() {
    const container = document.getElementById('feedbacks-list-container');
    if (!container) return;
    const note = (text) => container.replaceChildren(h('p', { class: 'w-muted post-empty', text }));
    try {
        const res = await authFetch('/api/feedbacks');
        if (!res.ok) {
            note('無法取得反饋紀錄');
            return;
        }
        const feedbacks = await res.json();
        if (!feedbacks.length) {
            note('目前沒有任何反饋。');
            return;
        }
        const isAdmin = localStorage.getItem('axis_role') === 'Administrator';
        container.replaceChildren(...feedbacks.map((f) => {
            const resolved = f.status === 'Resolved';
            let replyForm = null;
            if (!resolved && isAdmin) {
                const input = h('input', { type: 'text', id: `fb-reply-${f.id}`, class: 't-input', placeholder: '回覆內容' });
                input.addEventListener('keydown', (e) => { if (e.key === 'Enter') resolveFeedback(f.id); });
                replyForm = h('div', { class: 'post-reply-form' }, input,
                    h('button', { type: 'button', class: 'btn btn-primary btn-sm', text: '回覆並處置', onclick: () => resolveFeedback(f.id) }));
            }
            return h('article', { class: 'post-card' },
                h('div', { class: 'post-head' },
                    h('span', { class: 'pill muted', text: _FB_CATEGORY[f.category] || '其他' }),
                    h('h4', { class: 'post-title', text: f.title }),
                    h('span', { class: `pill ${resolved ? 'ok' : 'warn'}`, text: resolved ? '已處置' : '待處置' })),
                h('p', { class: 'post-body', text: f.content }),
                f.response ? h('div', { class: 'post-reply' },
                    h('span', { class: 'post-reply-label', text: '管理員回覆' }),
                    h('p', { text: f.response })) : null,
                h('div', { class: 'post-meta', text: `${f.creator} · ${shortTime(f.created_at)}` }),
                replyForm);
        }));
    } catch (e) {
        console.error('Failed to load feedbacks:', e);
        note('載入反饋時發生錯誤');
    }
}

async function submitFeedback() {
    const category = document.getElementById('feedback-category-input').value;
    const title = document.getElementById('feedback-title-input').value.trim();
    const content = document.getElementById('feedback-content-input').value.trim();
    if (!title || !content) {
        toastText('請填寫標題與內容', 'error');
        return;
    }
    try {
        const res = await authFetch('/api/feedbacks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, category })
        });
        if (res.ok) {
            toastText('反饋已送出，謝謝！', 'success');
            document.getElementById('feedback-title-input').value = '';
            document.getElementById('feedback-content-input').value = '';
            loadFeedbacks();
        } else {
            toastText(_fbDetail(await res.json().catch(() => null), '送出失敗'), 'error');
        }
    } catch (err) {
        console.error(err);
        toastText('連線錯誤，請稍後再試', 'error');
    }
}

async function resolveFeedback(id) {
    const input = document.getElementById(`fb-reply-${id}`);
    const response = input ? input.value.trim() : '';
    if (!response) {
        toastText('請輸入回覆內容', 'error');
        return;
    }
    try {
        const res = await authFetch(`/api/feedbacks/${encodeURIComponent(id)}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response })
        });
        if (res.ok) {
            toastText('已回覆並標記為已處置', 'success');
            loadFeedbacks();
        } else {
            toastText(_fbDetail(await res.json().catch(() => null), '操作失敗'), 'error');
        }
    } catch (err) {
        console.error(err);
        toastText('連線錯誤，請稍後再試', 'error');
    }
}

window.loadFeedbacks = loadFeedbacks;
window.submitFeedback = submitFeedback;
window.resolveFeedback = resolveFeedback;
