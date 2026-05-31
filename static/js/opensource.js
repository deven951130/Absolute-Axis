// Absolute Axis - Open Source Repos Module
async function loadGitHubRepos() {
    const grid = document.getElementById('repos-grid');
    if (!grid) return;

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
                        <a href="${repo.html_url}" target="_blank" class="btn btn-outline" style="padding:4px 10px; font-size:0.7rem; text-decoration:none;">查看原始碼</a>
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
}
