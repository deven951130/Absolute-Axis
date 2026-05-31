// Absolute Axis - Gig Platform Module
async function loadGigs() {
    const container = document.getElementById('gigs-list-container');
    if (!container) return;

    try {
        const res = await authFetch('/api/gigs');
        if (!res.ok) {
            container.innerHTML = '<div style="color:var(--text-muted); padding:2rem; text-align:center;">無法取得案件清單</div>';
            return;
        }
        const gigs = await res.json();
        
        container.innerHTML = '';
        if (gigs.length === 0) {
            container.innerHTML = '<div style="color:var(--text-muted); padding:3rem; text-align:center; font-weight:800;">目前沒有任何委託案件</div>';
            return;
        }

        const currentUser = localStorage.getItem('axis_user');

        gigs.forEach(g => {
            const item = document.createElement('div');
            item.className = 'file-list-item';
            item.style = 'display:flex; flex-direction:column; padding:1.5rem; gap:12px; margin-bottom:12px; border-radius:12px; border:1px solid var(--border-color); background:rgba(22, 27, 34, 0.4);';
            
            // 狀態與顏色標籤
            let statusBadge = '';
            if (g.status === 'Open') {
                statusBadge = '<span style="background:rgba(56, 139, 253, 0.15); color:#58a6ff; border:1px solid rgba(56, 139, 253, 0.4); padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:800;">開放承接</span>';
            } else if (g.status === 'Assigned') {
                statusBadge = '<span style="background:rgba(210, 153, 34, 0.15); color:#d29922; border:1px solid rgba(210, 153, 34, 0.4); padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:800;">進行中</span>';
            } else if (g.status === 'Completed') {
                statusBadge = '<span style="background:rgba(46, 160, 67, 0.15); color:#3fb950; border:1px solid rgba(46, 160, 67, 0.4); padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:800;">已完成</span>';
            }

            // 按鈕與操作控制
            let actionHtml = '';
            if (g.status === 'Open') {
                if (g.creator === currentUser) {
                    actionHtml = `<button class="btn btn-outline" style="color:var(--danger-color); padding:6px 12px; font-size:0.75rem;" onclick="deleteGig(${g.id})">撤回案件</button>`;
                } else {
                    actionHtml = `<button class="btn btn-primary" style="padding:6px 16px; font-size:0.75rem;" onclick="acceptGig(${g.id})">承接委託</button>`;
                }
            } else if (g.status === 'Assigned') {
                if (currentUser === g.creator || currentUser === g.worker || localStorage.getItem('axis_role') === 'Administrator') {
                    actionHtml = `<button class="btn btn-outline" style="color:#2ecc71; padding:6px 16px; font-size:0.75rem;" onclick="completeGig(${g.id})">標記為已完成</button>`;
                } else {
                    actionHtml = `<span style="font-size:0.75rem; color:var(--text-muted); font-weight:800;">承接人: ${g.worker}</span>`;
                }
            } else if (g.status === 'Completed') {
                actionHtml = `<span style="font-size:0.75rem; color:var(--text-muted); font-weight:800;">承接人: ${g.worker} (已驗收)</span>`;
            }

            item.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:8px;">
                    <div style="font-weight:900; font-size:1.1rem; color:var(--text-main);">${g.title}</div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        ${statusBadge}
                        <span style="font-weight:900; color:var(--accent-color); font-size:1rem;">$ ${g.budget} TWD</span>
                    </div>
                </div>
                <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.6; word-break:break-all;">
                    ${g.description.replace(/\n/g, '<br>')}
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px; font-size:0.72rem; color:var(--text-muted); font-weight:800;">
                    <div>
                        <span>發佈者: ${g.creator}</span>
                        <span style="margin: 0 10px;">|</span>
                        <span>時間: ${g.created_at.replace('T', ' ').substring(0, 19)}</span>
                    </div>
                    <div>
                        ${actionHtml}
                    </div>
                </div>
            `;
            container.appendChild(item);
        });
    } catch (e) {
        console.error("Failed to load gigs:", e);
    }
}

async function submitGig() {
    const titleVal = document.getElementById('gig-title-input').value.strip ? document.getElementById('gig-title-input').value.strip() : document.getElementById('gig-title-input').value.trim();
    const descVal = document.getElementById('gig-desc-input').value.strip ? document.getElementById('gig-desc-input').value.strip() : document.getElementById('gig-desc-input').value.trim();
    const budgetVal = parseInt(document.getElementById('gig-budget-input').value);

    if (!titleVal || !descVal || isNaN(budgetVal) || budgetVal <= 0) {
        if (typeof showToast === 'function') {
            showToast("請填寫完整的案件名稱、需求描述與有效的預算金額", "error");
        } else {
            alert("請填寫完整的案件資訊");
        }
        return;
    }

    try {
        const res = await authFetch('/api/gigs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: titleVal,
                description: descVal,
                budget: budgetVal
            })
        });

        if (res.ok) {
            if (typeof showToast === 'function') showToast("案件發佈成功", "success");
            document.getElementById('gig-title-input').value = '';
            document.getElementById('gig-desc-input').value = '';
            document.getElementById('gig-budget-input').value = '';
            loadGigs();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "發佈失敗", "error");
        }
    } catch (err) {
        console.error(err);
    }
}

async function acceptGig(id) {
    try {
        const res = await authFetch(`/api/gigs/${id}/accept`, { method: 'POST' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("已成功承接該委託案件", "success");
            loadGigs();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "承接失敗", "error");
        }
    } catch (e) {
        console.error(e);
    }
}

async function completeGig(id) {
    try {
        const res = await authFetch(`/api/gigs/${id}/complete`, { method: 'POST' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("案件已標記為完成", "success");
            loadGigs();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "操作失敗", "error");
        }
    } catch (e) {
        console.error(e);
    }
}

async function deleteGig(id) {
    if (!confirm("確定要撤回該案件嗎？")) return;
    try {
        const res = await authFetch(`/api/gigs/${id}`, { method: 'DELETE' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("已成功撤回案件", "success");
            loadGigs();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "撤回失敗", "error");
        }
    } catch (e) {
        console.error(e);
    }
}
