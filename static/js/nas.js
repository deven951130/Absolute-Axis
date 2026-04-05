/**
 * Absolute Axis - Private Cloud (NAS) Module V2.2
 * Refactored for modularity, robustness, and better UI feedback.
 */

const NASManager = {
    state: {
        currentPath: "",
        viewMode: localStorage.getItem('nas_view_mode') || 'grid',
        currentMode: 'drive',
        isLoaded: false,
        isLoading: false,
        shouldRestart: false
    },

    init() {
        console.log("--- NAS MODULE V2.2 INITIALIZING ---");
        this.updateViewButtons();
        // The actual loading will be triggered by switchView in ui.js
    },

    updateViewButtons() {
        const mode = this.state.viewMode;
        const btnGrid = document.getElementById('btn-grid');
        const btnList = document.getElementById('btn-list');
        if (!btnGrid || !btnList) return;

        const isLight = document.body.classList.contains('light-mode');
        const activeColor = isLight ? '#fff' : '#0d1117';
        
        btnGrid.style.background = (mode === 'grid' ? 'var(--accent-color)' : 'transparent');
        btnGrid.style.color = (mode === 'grid' ? activeColor : 'var(--text-main)');
        btnList.style.background = (mode === 'list' ? 'var(--accent-color)' : 'transparent');
        btnList.style.color = (mode === 'list' ? activeColor : 'var(--text-main)');
    },

    toggleView(mode) {
        this.state.viewMode = mode;
        localStorage.setItem('nas_view_mode', mode);
        this.updateViewButtons();
        this.loadFiles(this.state.currentPath);
    },

    async nav(m) {
        this.state.currentMode = m;
        this.state.currentPath = '';
        
        document.querySelectorAll('.nas-nav').forEach(e => e.classList.remove('active'));
        const navEl = document.getElementById('nas-nav-' + m);
        if (navEl) navEl.classList.add('active');
        
        await this.loadFiles('');
    },

    async loadFiles(path) {
        if (this.state.isLoading) return;
        this.state.isLoading = true;

        const exp = document.getElementById('nas-explorer');
        if (!exp) return;

        // Reset sidebar state if navigating from specific views
        if (path && (this.state.currentMode === 'starred' || this.state.currentMode === 'recent')) {
            this.state.currentMode = 'drive';
            document.querySelectorAll('.nas-nav').forEach(e => e.classList.remove('active'));
            const driveNav = document.getElementById('nas-nav-drive');
            if (driveNav) driveNav.classList.add('active');
        }
        
        this.state.currentPath = path;

        try {
            const res = await authFetch(`/api/nas/list?path=${encodeURIComponent(path)}&mode=${this.state.currentMode}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({detail: "Unknown error"}));
                throw new Error(err.detail || "伺服器回應錯誤");
            }
            
            const data = await res.json();
            this.renderExplorer(data);
            this.updateQuota(data);
            this.updateBreadcrumb(path);
            this.state.isLoaded = true;
        } catch (err) {
            console.error("NAS Load Error:", err);
            exp.innerHTML = `
                <div style="color:var(--danger-color); padding:3rem; width:100%; text-align:center;">
                    <div style="font-size:2.5rem; margin-bottom:1rem;">⚠️</div>
                    <div>無法載入雲端檔案：${err.message}</div>
                    <button class="btn btn-outline" style="margin-top:1.5rem;" onclick="NASManager.loadFiles('${path}')">再次嘗試</button>
                </div>
            `;
        } finally {
            this.state.isLoading = false;
        }
    },

    updateBreadcrumb(path) {
        const bc = document.getElementById('nas-breadcrumb');
        if (!bc) return;

        const modeNames = {
            'drive': '我的雲端硬碟',
            'shared': '與我共用',
            'starred': '已加星號',
            'recent': '近期存取',
            'trash': '回收站'
        };

        let html = `<span style="color:var(--text-muted); cursor:pointer;" onclick="NASManager.nav('${this.state.currentMode}')">${modeNames[this.state.currentMode]}</span>`;
        
        if (this.state.currentMode === 'drive') {
            const parts = path.split('/').filter(p => p);
            let cum = '';
            parts.forEach((p, i) => {
                cum += (i === 0 ? '' : '/') + p;
                html += ` <span style="color:var(--text-muted);">/</span> <span style="cursor:pointer;" onclick="NASManager.loadFiles('${cum}')">${p}</span>`;
            });
        }
        bc.innerHTML = html;
    },

    renderExplorer(data) {
        const exp = document.getElementById('nas-explorer');
        exp.className = (this.state.viewMode === 'grid' ? 'file-grid' : 'file-list');
        
        if (!data.files || data.files.length === 0) {
            exp.innerHTML = '<div style="color:var(--text-muted); padding:3rem; width:100%; text-align:center;">此目錄為空</div>';
            return;
        }

        exp.innerHTML = '';
        data.files.forEach(f => {
            const icon = f.is_dir ? '📁' : this.getFileIcon(f.ext);
            const fullPath = (this.state.currentMode === 'shared' ? f.path : ((this.state.currentPath ? this.state.currentPath + '/' : '') + f.name));
            const owner = f.owner || '';
            const item = this.createFileItem(f, icon, fullPath, owner);
            exp.appendChild(item);
        });
    },

    getFileIcon(ext) {
        const e = (ext || "").toLowerCase();
        if (['.jpg', '.png', '.jpeg', '.gif', '.webp'].includes(e)) return '🖼️';
        if (['.mp4', '.webm', '.mkv', '.avi'].includes(e)) return '🎬';
        if (['.mp3', '.wav', '.flac'].includes(e)) return '🎵';
        if (['.pdf'].includes(e)) return '📄';
        if (['.zip', '.rar', '.7z', '.tar', '.gz'].includes(e)) return '📦';
        if (['.iso'].includes(e)) return '💿';
        return '📄';
    },

    createFileItem(f, icon, fullPath, owner) {
        const item = document.createElement('div');
        const starIcon = f.starred ? '⭐' : '☆';
        const sizeText = f.is_dir ? '資料夾' : (f.size / 1024 / 1024).toFixed(1) + ' MB';

        if (this.state.viewMode === 'grid') {
            item.className = 'card file-card';
            item.onclick = f.is_dir ? () => this.loadFiles(fullPath) : () => this.previewFile(fullPath, f.ext, owner);
            item.oncontextmenu = (e) => this.showContextMenu(e, fullPath, f.is_dir, f.ext, owner);
            item.innerHTML = `
                <div style="position:absolute; top:12px; left:12px; cursor:pointer; font-size:1.1rem;" onclick="event.stopPropagation(); NASManager.toggleStar('${fullPath}')">${this.state.currentMode === 'drive' ? starIcon : ''}</div>
                <div style="font-size:2rem; margin-bottom:12px;">${icon}</div>
                <div style="font-weight:700; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; width:100%; text-align:center; color:var(--text-main);">${f.name}</div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">${sizeText}</div>
            `;
        } else {
            item.className = 'file-list-item';
            item.onclick = f.is_dir ? () => this.loadFiles(fullPath) : () => this.previewFile(fullPath, f.ext, owner);
            item.oncontextmenu = (e) => this.showContextMenu(e, fullPath, f.is_dir, f.ext, owner);
            item.innerHTML = `
                <div style="display:flex; align-items:center; gap:18px; flex:1; min-width:0;">
                    <span style="font-size:1.1rem; flex-shrink:0; cursor:pointer;" onclick="event.stopPropagation(); NASManager.toggleStar('${fullPath}')">${this.state.currentMode === 'drive' ? starIcon : ''}</span>
                    <div style="font-size:1.5rem; flex-shrink:0;">${icon}</div>
                    <div style="font-weight:700; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; color:var(--text-main);">${f.name}</div>
                </div>
                <div style="font-size:0.8rem; color:var(--text-muted); min-width:100px; text-align:right;">${sizeText}</div>
            `;
        }
        return item;
    },

    updateQuota(data) {
        const qBar = document.getElementById('quota-bar');
        const qLabel = document.getElementById('quota-label');
        if (!data || data.quota_used === undefined) return;

        const qP = (data.quota_used / data.quota_total * 100);
        if (qBar) qBar.style.width = Math.min(qP, 100) + '%';
        if (qBar) qBar.style.background = qP > 90 ? 'var(--danger-color)' : 'var(--accent-color)';
        
        if (qLabel) {
            const usedMB = (data.quota_used / 1024 / 1024).toFixed(0);
            const totalMB = (data.quota_total / 1024 / 1024).toFixed(0);
            qLabel.innerText = `${usedMB} MB / ${totalMB} MB`;
        }
    },

    async previewFile(path, ext, owner = '') {
        const url = `/api/nas/download?path=${encodeURIComponent(path)}${owner ? '&owner=' + encodeURIComponent(owner) : ''}`;
        const c = document.getElementById('preview-content');
        const n = document.getElementById('preview-filename');
        const modal = document.getElementById('modal-preview');
        
        if (!c || !n || !modal) return console.error("Preview modal components not found");
        
        n.innerText = path.split('/').pop();
        c.innerHTML = '<div style="color:#fff; font-size:1.2rem; padding:3rem; text-align:center;">⌛ 正在加載預覽...</div>';
        modal.style.display = 'flex';

        try {
            const res = await authFetch(url);
            if (!res.ok) throw new Error("檔案讀取失敗");
            
            const blob = await res.blob();
            const blobUrl = URL.createObjectURL(blob);
            const e = (ext || "").toLowerCase();

            if (['.jpg', '.png', '.gif', '.webp', '.jpeg'].includes(e)) {
                c.innerHTML = `<img src="${blobUrl}" style="max-width:100%; max-height:100%; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.5);">`;
            } else if (e === '.pdf') {
                c.innerHTML = `<iframe src="${blobUrl}" style="width:100%; height:100%; border:none; border-radius:12px;"></iframe>`;
            } else if (['.mp4', '.webm', '.ogg'].includes(e)) {
                c.innerHTML = `<video controls autoplay src="${blobUrl}" style="max-width:100%; max-height:100%; border-radius:12px;"></video>`;
            } else if (['.txt', '.md', '.py', '.json', '.js', '.html', '.css', '.c', '.cpp', '.h', '.java', '.go'].includes(e)) {
                const text = await blob.text();
                c.innerHTML = `<pre style="color:#fff; background:rgba(0,0,0,0.7); padding:30px; border-radius:12px; border:1px solid var(--border-color); width:100%; height:100%; overflow:auto; text-align:left; font-size:0.9rem; line-height:1.6; white-space:pre-wrap;">${this.escapeHTML(text)}</pre>`;
            } else {
                c.innerHTML = `
                    <div style="text-align:center;">
                        <div style="font-size:4rem; margin-bottom:20px;">📄</div>
                        <div style="color:var(--text-muted); margin-bottom:20px;">此檔案類型不支援線上預覽 (${e || '未知'})</div>
                        <button class="btn btn-primary" onclick="NASManager.download('${path}', '${owner}')">⬇️ 直接下載</button>
                    </div>
                `;
            }
        } catch (err) {
            c.innerHTML = `<div style="color:var(--danger-color); padding:3rem; text-align:center;">載入失敗：${err.message}</div>`;
        }
    },

    escapeHTML(text) {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    },

    closePreview() {
        const modal = document.getElementById('modal-preview');
        const c = document.getElementById('preview-content');
        if (modal) modal.style.display = 'none';
        if (c) c.innerHTML = '';
    },

    showContextMenu(e, path, isDir, ext, owner = '') {
        e.preventDefault(); e.stopPropagation();
        this.cmData = {path, isDir, ext, owner};
        const cm = document.getElementById('nas-context-menu');
        if (!cm) return;

        cm.style.display = 'block'; 
        cm.style.left = e.clientX + 'px'; 
        cm.style.top = e.clientY + 'px';
        
        // Context menu visibility logic
        const mode = this.state.currentMode;
        document.getElementById('cm-share').style.display = (mode === 'drive') ? 'flex' : 'none';
        document.getElementById('cm-star').style.display = (mode === 'drive') ? 'flex' : 'none';
        document.getElementById('cm-restore').style.display = (mode === 'trash') ? 'flex' : 'none';
        document.getElementById('cm-trash').style.display = (mode === 'drive') ? 'flex' : 'none';
        document.getElementById('cm-del').style.display = (mode === 'trash') ? 'flex' : 'none';
        document.getElementById('cm-open').innerText = isDir ? '📂 開啟資料夾' : '🔍 預覽檔案';
    },

    async cmAction(act) {
        const {path, isDir, ext, owner} = this.cmData;
        const cm = document.getElementById('nas-context-menu');
        if (cm) cm.style.display = 'none';

        try {
            if (act === 'open') { if (isDir) this.loadFiles(path); else this.previewFile(path, ext, owner); }
            if (act === 'dl') this.download(path, owner);
            if (act === 'share') this.openShare(path);
            if (act === 'star') await this.toggleStar(path);
            if (act === 'trash') await this.moveToTrash(path);
            if (act === 'restore') { 
                await authFetch('/api/nas/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path})});
                this.loadFiles('');
            }
            if (act === 'delete') { 
                if (confirm('永久刪除此項目？此操作不可恢復！')) { 
                    await authFetch('/api/nas/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path})});
                    this.loadFiles('');
                } 
            }
        } catch (err) {
            alert("操作失敗：" + err.message);
        }
    },

    async toggleStar(path) {
        try {
            const res = await authFetch('/api/nas/toggle_star', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({path})
            });
            if (res.ok) this.loadFiles(this.state.currentPath);
        } catch (err) { console.error(err); }
    },

    async moveToTrash(path) {
        try {
            const res = await authFetch('/api/nas/trash', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({path})
            });
            if (res.ok) this.loadFiles(this.state.currentPath);
        } catch (err) { console.error(err); }
    },

    async download(path, owner = '') {
        try {
            const url = `/api/nas/download?path=${encodeURIComponent(path)}${owner ? '&owner=' + encodeURIComponent(owner) : ''}`;
            const res = await authFetch(url); 
            if (res.ok) {
                const blob = await res.blob(); 
                const u = URL.createObjectURL(blob); 
                const a = document.createElement('a'); 
                a.href = u; 
                a.download = path.split('/').pop(); 
                a.click();
                setTimeout(() => URL.revokeObjectURL(u), 100);
            } else {
                alert("下載失敗");
            }
        } catch (err) { console.error(err); }
    },

    promptMkdir() {
        const menu = document.getElementById('new-menu');
        if (menu) menu.style.display = 'none';
        
        const modal = document.getElementById('modal-mkdir');
        const input = document.getElementById('mkdir-name');
        if (modal && input) {
            input.value = "";
            modal.style.display = 'flex';
            input.focus();
        }
    },

    async confirmMkdir() {
        const input = document.getElementById('mkdir-name');
        const name = (input ? input.value.trim() : "");
        if (!name) return alert("請輸入名稱");
        
        try {
            const res = await authFetch('/api/nas/mkdir', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({path: this.state.currentPath, name: name})
            });
            
            if (res.ok) {
                document.getElementById('modal-mkdir').style.display = 'none';
                this.loadFiles(this.state.currentPath);
            } else {
                const err = await res.json().catch(() => ({}));
                alert("建立失敗：" + (err.detail || "名稱衝突或權限不足"));
            }
        } catch (err) { alert("連線錯誤"); }
    },

    async openShare(path) {
        try {
            const res = await authFetch('/api/nas/users');
            if (!res.ok) return alert("無法獲取使用者列表");
            
            const users = await res.json();
            const sel = document.getElementById('share-user-select');
            if (sel) {
                sel.innerHTML = users.map(u => `<option value="${u.username}">${u.username}</option>`).join('');
            }
            
            const targetName = document.getElementById('share-target-name');
            if (targetName) targetName.innerText = path.split('/').pop();
            
            const modal = document.getElementById('modal-share');
            if (modal) {
                modal.setAttribute('data-path', path);
                modal.style.display = 'flex';
            }
        } catch (err) { console.error(err); }
    },

    async confirmShare() {
        const modal = document.getElementById('modal-share');
        const path = modal.getAttribute('data-path');
        const target = document.getElementById('share-user-select').value;
        if (!target) return alert('請選擇對象');
        
        try {
            const res = await authFetch('/api/nas/share', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: path, target_user: target})
            });
            if (res.ok) modal.style.display = 'none';
            else alert("共用設定失敗");
        } catch (err) { console.error(err); }
    },

    async upload() {
        const input = document.getElementById('nas-up');
        if (!input || !input.files.length) return;
        
        const file = input.files[0];
        const mon = document.getElementById('upload-monitor');
        const bar = document.getElementById('up-bar');
        const speed = document.getElementById('up-speed');
        const name = document.getElementById('up-filename');

        if (mon) mon.style.display = 'block';
        if (name) name.innerText = file.name;
        if (bar) bar.style.width = '0%';
        if (speed) speed.innerText = '-- MB/s';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', this.state.currentPath);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/nas/upload', true);
        xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        
        const startTime = Date.now();
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = (e.loaded / e.total * 100).toFixed(1);
                if (bar) bar.style.width = pct + '%';
                const duration = (Date.now() - startTime) / 1000;
                if (duration > 0 && speed) {
                    const mbps = (e.loaded / 1024 / 1024 / duration).toFixed(1);
                    speed.innerText = mbps + ' MB/s';
                }
            }
        };
        
        xhr.onload = async () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                if (this.state.shouldRestart) {
                    if (name) name.innerText = "正在重新啟動伺服器...";
                    if (bar) bar.style.background = "var(--success-color)";
                    try { await authFetch('/api/action/restart', {method:'POST'}); } catch(e) {}
                    setTimeout(() => location.reload(), 3000); // 3 秒後重新整理網頁
                } else {
                    setTimeout(() => {
                        if (mon) mon.style.display = 'none';
                        this.loadFiles(this.state.currentPath);
                    }, 800);
                }
            } else {
                let detail = "上傳失敗";
                try { detail = JSON.parse(xhr.responseText).detail || detail; } catch(e) {}
                alert("錯誤：" + detail);
                if (mon) mon.style.display = 'none';
            }
        };
        
        xhr.onerror = () => {
            alert('網路連線錯誤，上傳失敗');
            if (mon) mon.style.display = 'none';
        };
        
        xhr.send(formData);
    },

    triggerUpload(restart = false) {
        this.state.shouldRestart = restart;
        const input = document.getElementById('nas-up');
        if (input) input.click();
        const menu = document.getElementById('new-menu');
        if (menu) menu.style.display = 'none';
    }
};

// Global Exposure for Legacy Event Handlers
window.toggleNASView = (m) => NASManager.toggleView(m);
window.nasNav = (m) => NASManager.nav(m);
window.loadNASFiles = (p) => NASManager.loadFiles(p);
window.promptMkdir = () => NASManager.promptMkdir();
window.confirmMkdir = () => NASManager.confirmMkdir();
window.triggerUpload = (r) => NASManager.triggerUpload(r);
window.nasUpload = () => NASManager.upload();
window.previewFile = (p, e, o) => NASManager.previewFile(p, e, o);
window.closePreview = () => NASManager.closePreview();
window.cmAction = (a) => NASManager.cmAction(a);
window.confirmShare = () => NASManager.confirmShare();

// Initialization
document.addEventListener('DOMContentLoaded', () => NASManager.init());

// Close context menu on click
window.addEventListener('click', () => {
    const cm = document.getElementById('nas-context-menu');
    if (cm) cm.style.display = 'none';
});