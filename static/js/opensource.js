// Absolute Axis - Open Source Repos Module
async function loadGitHubRepos() {
    const grid = document.getElementById('repos-grid');
    if (!grid) return;

    // 處理管理員新增專案按鈕顯示
    const role = localStorage.getItem('axis_role');
    const isAdmin = (role === 'admin' || role === 'Administrator');
    const addBtn = document.getElementById('os-add-repo-btn');
    if (addBtn) addBtn.style.display = isAdmin ? 'block' : 'none';

    try {
        const res = await authFetch('/api/github/repos');
        if (!res.ok) {
            grid.innerHTML = '<div style="color:var(--text-muted); padding:2rem; text-align:center; grid-column: 1 / span 2;">無法取得開源專案數據</div>';
            return;
        }
        const repos = await res.json();
        
        grid.innerHTML = '';
        if (repos.length === 0) {
            grid.innerHTML = '<div style="color:var(--text-muted); padding:3rem; text-align:center; font-weight:800; grid-column: 1 / span 2;">沒有發現任何公開專案</div>';
            return;
        }

        repos.forEach(repo => {
            const card = document.createElement('div');
            card.className = 'card';
            card.style = 'display:flex; flex-direction:column; justify-content:space-between; gap:15px; border-radius:12px; transition: transform 0.2s, border-color 0.2s; background: rgba(22, 27, 34, 0.4);';
            
            // 當前語言的背景顏色提示
            const lang = repo.language || 'Unknown';
            let langColor = '#8b949e';
            if (lang === 'Python') langColor = '#3572A5';
            else if (lang === 'JavaScript') langColor = '#f1e05a';
            else if (lang === 'TypeScript') langColor = '#3178c6';
            else if (lang === 'HTML') langColor = '#e34c26';
            else if (lang === 'CSS') langColor = '#563d7c';
            else if (lang === 'Shell') langColor = '#89e051';

            const cloneCmd = `git clone ${repo.html_url}.git`;
            
            // 僅限管理員顯示刪除按鈕
            let deleteBtnHtml = '';
            if (isAdmin) {
                deleteBtnHtml = `<button class="btn btn-outline" style="padding:4px 10px; font-size:0.7rem; color:var(--danger-color); border-color:var(--danger-color) !important; margin-right:8px;" onclick="window.deleteRepo('${repo.name}')">刪除專案</button>`;
            }

            card.innerHTML = `
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <h4 style="margin:0; font-size:1.1rem; font-weight:900; color:var(--accent-color);">${repo.name}</h4>
                        <div style="display:flex; gap:10px; font-size:0.75rem; font-weight:800; color:var(--text-muted);">
                            <span>★ ${repo.stars}</span>
                            <span>⇅ ${repo.forks}</span>
                        </div>
                    </div>
                    <p style="font-size:0.8rem; color:var(--text-muted); line-height:1.5; margin-bottom:15px; min-height:40px; word-break:break-all;">
                        ${repo.description || '無專案描述。'}
                    </p>
                </div>
                <div>
                    <!-- Clone 命令複製面板 -->
                    <div style="display:flex; align-items:center; background:rgba(0,0,0,0.3); border:1px solid var(--border-color); padding:6px 12px; border-radius:6px; margin-bottom:12px;">
                        <code style="font-family:monospace; font-size:0.72rem; color:#7ee787; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${cloneCmd}</code>
                        <button class="btn btn-outline" style="padding:2px 8px; font-size:0.65rem; font-weight:800; margin-left:8px;" onclick="copyCloneCommand('${cloneCmd}')">複製</button>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-color); padding-top:10px; font-size:0.7rem; color:var(--text-muted); font-weight:800;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${langColor};"></span>
                            <span>${lang}</span>
                        </div>
                        <div style="display:flex; align-items:center;">
                            ${deleteBtnHtml}
                            <a href="${repo.html_url}" target="_blank" class="btn btn-outline" style="padding:4px 10px; font-size:0.7rem; text-decoration:none;">查看原始碼</a>
                        </div>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (e) {
        console.error("Failed to load repos:", e);
    }
}

window.copyCloneCommand = function(text) {
    navigator.clipboard.writeText(text).then(() => {
        if (typeof showToast === 'function') {
            showToast("已成功複製 Clone 指令", "success");
        } else {
            alert("已複製");
        }
    }).catch(err => {
        console.error('Could not copy text: ', err);
    });
};

window.showAddRepoModal = function() {
    const modal = document.getElementById('os-add-repo-modal');
    if (modal) {
        document.getElementById('os-import-url').value = '';
        document.getElementById('os-repo-name').value = '';
        document.getElementById('os-repo-fullname').value = '';
        document.getElementById('os-repo-url').value = '';
        document.getElementById('os-repo-lang').value = '';
        document.getElementById('os-repo-desc').value = '';
        
        const btn = document.getElementById('os-import-btn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = '解析';
        }
        modal.style.display = 'flex';
    }
};

window.hideAddRepoModal = function() {
    const modal = document.getElementById('os-add-repo-modal');
    if (modal) modal.style.display = 'none';
};

window.importFromUrl = async function() {
    const urlInput = document.getElementById('os-import-url');
    const btn = document.getElementById('os-import-btn');
    if (!urlInput || !btn) return;
    
    const url = urlInput.value.trim();
    if (!url) {
        if (typeof showToast === 'function') showToast("請貼上有效的 GitHub 專案連結！", "error");
        return;
    }
    
    btn.disabled = true;
    btn.textContent = '解析中...';
    
    try {
        const res = await authFetch('/api/github/parse-url?url=' + encodeURIComponent(url));
        const data = await res.json();
        
        if (res.ok) {
            document.getElementById('os-repo-name').value = data.name || '';
            document.getElementById('os-repo-fullname').value = data.full_name || '';
            document.getElementById('os-repo-url').value = data.html_url || '';
            document.getElementById('os-repo-lang').value = data.language || '';
            document.getElementById('os-repo-desc').value = data.description || '';
            
            if (typeof showToast === 'function') showToast("成功解析並自動填入專案資訊！", "success");
        } else {
            if (typeof showToast === 'function') showToast(data.detail || "解析專案連結失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("網路錯誤：" + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = '解析';
    }
};

window.submitAddRepo = async function() {
    let name = document.getElementById('os-repo-name').value.trim();
    let fullname = document.getElementById('os-repo-fullname').value.trim();
    let url = document.getElementById('os-repo-url').value.trim();
    let lang = document.getElementById('os-repo-lang').value.trim();
    let desc = document.getElementById('os-repo-desc').value.trim();
    
    const importUrlInput = document.getElementById('os-import-url');
    const importUrl = importUrlInput ? importUrlInput.value.trim() : '';
    
    // 如果主要欄位空白但有填匯入網址，則自動進行一次解析
    if ((!name || !fullname || !url) && importUrl) {
        if (typeof showToast === 'function') showToast("檢測到匯入連結，正在自動解析中...", "info");
        
        const btn = document.getElementById('os-import-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '解析中...';
        }
        
        try {
            const res = await authFetch('/api/github/parse-url?url=' + encodeURIComponent(importUrl));
            if (res.ok) {
                const data = await res.json();
                name = data.name || '';
                fullname = data.full_name || '';
                url = data.html_url || '';
                lang = data.language || lang;
                desc = data.description || desc;
                
                // 同步填回 UI
                document.getElementById('os-repo-name').value = name;
                document.getElementById('os-repo-fullname').value = fullname;
                document.getElementById('os-repo-url').value = url;
                document.getElementById('os-repo-lang').value = lang;
                document.getElementById('os-repo-desc').value = desc;
            } else {
                const data = await res.json();
                if (typeof showToast === 'function') showToast(data.detail || "自動解析失敗，請手動填寫或重新檢查連結", "error");
                return;
            }
        } catch (e) {
            if (typeof showToast === 'function') showToast("自動解析網路錯誤：" + e.message, "error");
            return;
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '解析';
            }
        }
    }
    
    if (!name || !fullname || !url) {
        if (typeof showToast === 'function') showToast("請填寫專案名稱、完整名稱與專案連結！", "error");
        return;
    }
    
    try {
        const res = await authFetch('/api/github/repos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                full_name: fullname,
                html_url: url,
                language: lang || "JavaScript",
                description: desc
            })
        });
        
        if (res.ok) {
            if (typeof showToast === 'function') showToast("已成功新增開源專案！", "success");
            window.hideAddRepoModal();
            await loadGitHubRepos();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "新增專案失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("網路錯誤：" + e.message, "error");
    }
};

window.deleteRepo = async function(name) {
    const ok = confirm(`您確定要刪除開源專案「${name}」嗎？`);
    if (!ok) return;
    
    try {
        const res = await authFetch(`/api/github/repos/${name}`, { method: 'DELETE' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("已成功刪除該開源專案！", "success");
            await loadGitHubRepos();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "刪除專案失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("網路錯誤：" + e.message, "error");
    }
};

