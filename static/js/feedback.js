// Absolute Axis - Feedback Hub Module
async function loadFeedbacks() {
    const container = document.getElementById('feedbacks-list-container');
    if (!container) return;

    try {
        const res = await authFetch('/api/feedbacks');
        if (!res.ok) {
            container.innerHTML = '<div style="color:var(--text-muted); padding:2rem; text-align:center;">無法取得意見反饋紀錄</div>';
            return;
        }
        const feedbacks = await res.json();
        
        container.innerHTML = '';
        if (feedbacks.length === 0) {
            container.innerHTML = '<div style="color:var(--text-muted); padding:3rem; text-align:center; font-weight:800;">目前沒有任何意見反饋紀錄</div>';
            return;
        }

        const isAdmin = localStorage.getItem('axis_role') === 'Administrator';

        feedbacks.forEach(f => {
            const item = document.createElement('div');
            item.className = 'file-list-item';
            item.style = 'display:flex; flex-direction:column; padding:1.5rem; gap:12px; margin-bottom:12px; border-radius:12px; border:1px solid var(--border-color); background:rgba(22, 27, 34, 0.4);';
            
            // 分類與狀態標籤
            let cateText = '其他';
            if (f.category === 'Bug') cateText = '系統錯誤';
            else if (f.category === 'Suggestion') cateText = '功能建議';
            
            const cateBadge = `<span style="background:rgba(255,255,255,0.06); color:var(--text-muted); border:1px solid var(--border-color); padding:2px 8px; border-radius:4px; font-size:0.65rem; font-weight:800; margin-right:8px;">${cateText}</span>`;
            
            const statusBadge = f.status === 'Resolved' ?
                '<span style="background:rgba(46, 160, 67, 0.15); color:#3fb950; border:1px solid rgba(46, 160, 67, 0.4); padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:800;">已處置</span>' :
                '<span style="background:rgba(248, 81, 73, 0.15); color:#f85149; border:1px solid rgba(248, 81, 73, 0.4); padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:800;">待處置</span>';

            // 管理員回覆區塊
            let adminActionHtml = '';
            if (f.status === 'Pending' && isAdmin) {
                adminActionHtml = `
                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border-color); display:flex; gap:10px;">
                        <input type="text" id="fb-reply-${f.id}" placeholder="請輸入回覆內容" class="t-input" style="flex:1; height:36px;">
                        <button class="btn btn-primary" style="padding:0 16px; font-size:0.75rem; height:36px;" onclick="resolveFeedback(${f.id})">回覆並處置</button>
                    </div>
                `;
            }

            // 顯示管理員的回覆
            let responseHtml = '';
            if (f.response) {
                responseHtml = `
                    <div style="background:rgba(56, 139, 253, 0.05); border-left:3px solid var(--accent-color); padding:10px 15px; border-radius:4px; margin-top:8px;">
                        <div style="font-size:0.7rem; font-weight:800; color:var(--accent-color); margin-bottom:4px;">系統管理員回覆</div>
                        <div style="font-size:0.8rem; color:var(--text-main); line-height:1.5;">${f.response}</div>
                    </div>
                `;
            }

            item.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:8px;">
                    <div style="display:flex; align-items:center;">
                        ${cateBadge}
                        <span style="font-weight:900; font-size:1rem; color:var(--text-main);">${f.title}</span>
                    </div>
                    <div>
                        ${statusBadge}
                    </div>
                </div>
                <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.6; word-break:break-all;">
                    ${f.content.replace(/\n/g, '<br>')}
                </div>
                ${responseHtml}
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px; font-size:0.72rem; color:var(--text-muted); font-weight:800;">
                    <div>
                        <span>提交者: ${f.creator}</span>
                        <span style="margin: 0 10px;">|</span>
                        <span>時間: ${f.created_at.replace('T', ' ').substring(0, 19)}</span>
                    </div>
                </div>
                ${adminActionHtml}
            `;
            container.appendChild(item);
        });
    } catch (e) {
        console.error("Failed to load feedbacks:", e);
    }
}

async function submitFeedback() {
    const categoryVal = document.getElementById('feedback-category-input').value;
    const titleVal = document.getElementById('feedback-title-input').value.strip ? document.getElementById('feedback-title-input').value.strip() : document.getElementById('feedback-title-input').value.trim();
    const contentVal = document.getElementById('feedback-content-input').value.strip ? document.getElementById('feedback-content-input').value.strip() : document.getElementById('feedback-content-input').value.trim();

    if (!titleVal || !contentVal) {
        if (typeof showToast === 'function') {
            showToast("請填寫完整的反饋主題與詳細描述", "error");
        } else {
            alert("請填寫完整資訊");
        }
        return;
    }

    try {
        const res = await authFetch('/api/feedbacks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: titleVal,
                content: contentVal,
                category: categoryVal
            })
        });

        if (res.ok) {
            if (typeof showToast === 'function') showToast("意見反饋送出成功", "success");
            document.getElementById('feedback-title-input').value = '';
            document.getElementById('feedback-content-input').value = '';
            loadFeedbacks();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "提交失敗", "error");
        }
    } catch (err) {
        console.error(err);
    }
}

async function resolveFeedback(id) {
    const replyInput = document.getElementById(`fb-reply-${id}`);
    const replyVal = replyInput.value.strip ? replyInput.value.strip() : replyInput.value.trim();
    if (!replyVal) {
        if (typeof showToast === 'function') showToast("請輸入回覆內容", "error");
        return;
    }

    try {
        const res = await authFetch(`/api/feedbacks/${id}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response: replyVal })
        });

        if (res.ok) {
            if (typeof showToast === 'function') showToast("處置意見反饋成功", "success");
            loadFeedbacks();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "操作失敗", "error");
        }
    } catch (err) {
        console.error(err);
    }
}
