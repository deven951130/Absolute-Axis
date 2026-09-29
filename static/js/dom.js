/**
 * Absolute Axis - 各頁共用的安全小工具
 * - h()：建立元素；文字一律 textContent，事件用 addEventListener（不組 HTML／onclick 字串）
 * - toastText()：showToast() 會把訊息插入 HTML，這裡先跳脫
 * - axisAsk()：頁內確認／輸入視窗，取代原生 confirm()／prompt()（有些內嵌瀏覽器會擋掉，危險操作就被默默取消）
 * 來自使用者或伺服器的文字（帳號名稱、案件、反饋…）一律經過這些工具顯示。
 */

function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        if (v == null || v === false) continue;
        if (k === 'class') el.className = v;
        else if (k === 'text') el.textContent = v;
        else if (k === 'dataset') Object.assign(el.dataset, v);
        else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? '' : String(v));
    }
    for (const c of children.flat()) {
        if (c != null && c !== false) el.append(c);
    }
    return el;
}

function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function toastText(message, type = 'info') {
    if (typeof showToast === 'function') showToast(escapeHTML(message), type);
}

// 「2026-09-29T12:34:56」→「2026-09-29 12:34」
function shortTime(iso) {
    return String(iso || '').replace('T', ' ').substring(0, 16);
}

function _axisAskDialog() {
    let dlg = document.getElementById('axis-ask');
    if (dlg) return dlg;
    dlg = h('dialog', { id: 'axis-ask', class: 'axis-ask', 'aria-labelledby': 'axis-ask-title' },
        h('p', { id: 'axis-ask-title', class: 'axis-ask-title' }),
        h('p', { id: 'axis-ask-msg', class: 'axis-ask-msg' }),
        h('input', { id: 'axis-ask-input', class: 't-input', type: 'text', autocomplete: 'off' }),
        h('div', { class: 'axis-ask-actions' },
            h('button', { id: 'axis-ask-cancel', type: 'button', class: 'btn btn-outline', text: '取消' }),
            h('button', { id: 'axis-ask-ok', type: 'button', class: 'btn btn-primary', text: '確定' })));
    document.body.append(dlg);
    return dlg;
}

/**
 * axisAsk({ title, message, ok, cancel, danger })      → Promise<boolean>（取消鈕文字可自訂）
 * axisAsk({ title, message, ok, input: '', placeholder }) → Promise<string|null>（取消 = null）
 */
function axisAsk({ title, message = '', ok = '確定', cancel = '取消', danger = false, input = null, placeholder = '' }) {
    const dlg = _axisAskDialog();
    if (typeof dlg.showModal !== 'function') {  // 極舊的瀏覽器：退回原生視窗
        return Promise.resolve(input === null ? window.confirm(`${title}\n\n${message}`) : window.prompt(title, input));
    }
    const field = document.getElementById('axis-ask-input');
    const okBtn = document.getElementById('axis-ask-ok');
    const cancelBtn = document.getElementById('axis-ask-cancel');
    document.getElementById('axis-ask-title').textContent = title;
    const msg = document.getElementById('axis-ask-msg');
    msg.textContent = message;
    msg.hidden = !message;
    field.hidden = input === null;
    field.value = input === null ? '' : input;
    field.placeholder = placeholder;
    okBtn.textContent = ok;
    cancelBtn.textContent = cancel;
    okBtn.className = danger ? 'btn btn-danger-solid' : 'btn btn-primary';
    return new Promise((resolve) => {
        const done = (value) => {
            okBtn.onclick = cancelBtn.onclick = dlg.oncancel = field.onkeydown = null;
            if (dlg.open) dlg.close();
            resolve(value);
        };
        okBtn.onclick = () => done(input === null ? true : field.value);
        cancelBtn.onclick = () => done(input === null ? false : null);
        dlg.oncancel = (e) => { e.preventDefault(); done(input === null ? false : null); };  // Esc
        field.onkeydown = (e) => { if (e.key === 'Enter') okBtn.click(); };
        dlg.showModal();
        (input === null ? cancelBtn : field).focus();  // 危險確認預設停在「取消」
    });
}

window.h = h;
window.escapeHTML = escapeHTML;
window.toastText = toastText;
window.shortTime = shortTime;
window.axisAsk = axisAsk;
