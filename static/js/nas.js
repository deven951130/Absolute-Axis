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
        btnGrid.setAttribute('aria-pressed', String(mode === 'grid'));
        btnList.setAttribute('aria-pressed', String(mode === 'list'));
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

        this.state.currentPath = path;
        localStorage.setItem('nas_current_path', path);

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
                const errData = await res.json().catch(() => ({detail: "伺服器內部錯誤"}));
                throw new Error(errData.detail || "無法存取雲端空間");
            }
            const data = await res.json();
            this.renderExplorer(data);
            this.updateQuota(data);
            this.updateBreadcrumb(path);
            this.state.isLoaded = true;
        } catch (err) {
            console.error("NAS Load Error:", err);
            const box = document.createElement('div');
            box.className = 'files-empty';
            const t = document.createElement('div');
            t.style.color = 'var(--danger-color)';
            t.style.fontWeight = '600';
            t.textContent = '載入失敗';
            const msg = document.createElement('div');
            msg.className = 'w-muted';
            msg.style.fontSize = '13px';
            msg.textContent = err.message;
            const retry = document.createElement('button');
            retry.type = 'button';
            retry.className = 'btn btn-outline';
            retry.style.marginTop = '12px';
            retry.textContent = '再試一次';
            retry.addEventListener('click', () => this.loadFiles(path));
            box.append(t, msg, retry);
            exp.replaceChildren(box);
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
            'recent': '最近使用',
            'trash': '最近刪除'
        };
        // 檔名／資料夾名稱來自使用者上傳：一律 textContent，點擊用閉包，不組 HTML 字串
        const link = (text, onclick, muted) => {
            const s = document.createElement('button');
            s.type = 'button';
            s.className = 'crumb' + (muted ? ' muted' : '');
            s.textContent = text;
            s.addEventListener('click', onclick);
            return s;
        };
        const sep = () => { const s = document.createElement('span'); s.className = 'crumb-sep'; s.textContent = '›'; return s; };
        const nodes = [link(modeNames[this.state.currentMode], () => this.nav(this.state.currentMode), !!path)];
        if (this.state.currentMode === 'drive') {
            const parts = path.split('/').filter(p => p);
            let cum = '';
            parts.forEach((p, i) => {
                cum += (i === 0 ? '' : '/') + p;
                const target = cum;
                nodes.push(sep(), link(p, () => this.loadFiles(target), i < parts.length - 1));
            });
        }
        bc.replaceChildren(...nodes);
    },

    renderExplorer(data) {
        const exp = document.getElementById('nas-explorer');
        exp.className = (this.state.viewMode === 'grid' ? 'file-grid' : 'file-list');

        if (!data.files || data.files.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'files-empty';
            empty.innerHTML = '<svg viewBox="0 0 64 52" aria-hidden="true"><path d="M4 10a6 6 0 0 1 6-6h14l6 6h24a6 6 0 0 1 6 6v26a6 6 0 0 1-6 6H10a6 6 0 0 1-6-6z" fill="currentColor" opacity=".35"></path></svg>';
            const t = document.createElement('div');
            t.textContent = this.state.currentMode === 'trash' ? '沒有最近刪除的項目' : '這裡還沒有檔案';
            const sub = document.createElement('div');
            sub.className = 'w-muted';
            sub.style.fontSize = '13px';
            sub.textContent = this.state.currentMode === 'drive' ? '按右上角「＋ 新增」上傳檔案或建立資料夾' : '';
            empty.append(t, sub);
            exp.replaceChildren(empty);
            return;
        }

        exp.replaceChildren();
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

    // 像「檔案」App 的圖示：資料夾是藍色資料夾；檔案是一張紙，下方色帶寫副檔名
    fileIconSvg(f) {
        if (f.is_dir) {
            return '<svg viewBox="0 0 64 52" aria-hidden="true"><path d="M4 10a6 6 0 0 1 6-6h14l6 6h24a6 6 0 0 1 6 6v26a6 6 0 0 1-6 6H10a6 6 0 0 1-6-6z" fill="#6BBDFA"></path><path d="M4 18a6 6 0 0 1 6-6h44a6 6 0 0 1 6 6v24a6 6 0 0 1-6 6H10a6 6 0 0 1-6-6z" fill="#3E9BF0"></path></svg>';
        }
        const e = (f.ext || '').toLowerCase();
        const kinds = [
            [['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.svg'], '#2FB463'],
            [['.mp4', '.webm', '.mkv', '.avi', '.mov'], '#A45DE0'],
            [['.mp3', '.wav', '.flac', '.m4a'], '#FF375F'],
            [['.pdf'], '#FF453A'],
            [['.zip', '.rar', '.7z', '.tar', '.gz'], '#A2845E'],
            [['.txt', '.md', '.json', '.py', '.js', '.html', '.css', '.log', '.yml', '.yaml'], '#3E7BFA'],
        ];
        const color = (kinds.find(([exts]) => exts.includes(e)) || [null, '#8E8E93'])[1];
        const label = e.replace('.', '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4) || 'FILE';
        return `<svg viewBox="0 0 48 60" aria-hidden="true"><path d="M6 2h26l12 12v40a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z" fill="#F5F5F7"></path><path d="M32 2v10a2 2 0 0 0 2 2h10z" fill="#D5D5DB"></path><rect x="2" y="36" width="44" height="13" fill="${color}"></rect><text x="24" y="45.6" text-anchor="middle" font-size="8.5" font-weight="700" fill="#FFFFFF" font-family="-apple-system, Geist, sans-serif">${label}</text></svg>`;
    },

    formatSize(bytes) {
        if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
        if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
        if (bytes >= 1024) return Math.round(bytes / 1024) + ' KB';
        return (bytes || 0) + ' B';
    },

    createFileItem(f, icon, fullPath, owner) {
        const grid = this.state.viewMode === 'grid';
        const item = document.createElement('div');
        item.className = grid ? 'card file-card fx-card' : 'file-list-item fx-row';
        item.tabIndex = 0;
        item.setAttribute('role', 'button');
        const open = f.is_dir ? () => this.loadFiles(fullPath) : () => this.previewFile(fullPath, f.ext, owner);
        item.addEventListener('click', open);
        item.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
        item.oncontextmenu = (e) => this.showContextMenu(e, fullPath, f.is_dir, f.ext, owner);

        const star = document.createElement('button');
        star.type = 'button';
        star.className = 'fx-star' + (f.starred ? ' on' : '');
        star.textContent = f.starred ? '★' : '☆';
        star.setAttribute('aria-label', f.starred ? '移除星號' : '加上星號');
        star.hidden = this.state.currentMode !== 'drive';
        star.addEventListener('click', (e) => { e.stopPropagation(); this.toggleStar(fullPath); });

        const ic = document.createElement('div');
        ic.className = 'fx-icon';
        ic.innerHTML = this.fileIconSvg(f);
        const name = document.createElement('div');
        name.className = 'fx-name';
        name.textContent = f.name;
        name.title = f.name;
        const meta = document.createElement('div');
        meta.className = 'fx-meta';
        meta.textContent = f.is_dir ? '資料夾' : this.formatSize(f.size);

        item.append(star, ic, name, meta);
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
            const formatSize = (bytes) => {
                if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
                return (bytes / 1048576).toFixed(0) + ' MB';
            };
            qLabel.innerText = `${formatSize(data.quota_used)} / ${formatSize(data.quota_total)}`;
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
                // 路徑與副檔名來自檔名：用 DOM＋textContent＋事件綁定，不組 onclick 字串（檔名含引號時可注入）
                const box = document.createElement('div');
                box.style.textAlign = 'center';
                const icon = document.createElement('div');
                icon.style.cssText = 'font-size:4rem; margin-bottom:20px;';
                icon.textContent = '📄';
                const msg = document.createElement('div');
                msg.style.cssText = 'color:var(--text-muted); margin-bottom:20px;';
                msg.textContent = `此檔案類型不支援線上預覽 (${e || '未知'})`;
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-primary';
                btn.textContent = '⬇️ 直接下載';
                btn.addEventListener('click', () => NASManager.download(path, owner));
                box.append(icon, msg, btn);
                c.replaceChildren(box);
            }
        } catch (err) {
            const fail = document.createElement('div');
            fail.style.cssText = 'color:var(--danger-color); padding:3rem; text-align:center;';
            fail.textContent = `載入失敗：${err.message}`;
            c.replaceChildren(fail);
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
                // 使用者名稱來自伺服器：用 Option（textContent／value），不插入 HTML
                sel.replaceChildren(...users.map((u) => new Option(u.username, u.username)));
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
        
        // Cloudflare Free Tier 100MB limit check
        if (file.size > 100 * 1024 * 1024 && window.location.hostname.includes('dpdns.org')) {
            if (!confirm('偵測到您正透過 Cloudflare 代理上傳超過 100MB 的檔案。Cloudflare 免費版通常限制單次上傳為 100MB，這可能會導致上傳失敗。是否仍要嘗試？\n\n建議：如需上傳大檔案，請使用 Tailscale 內網 IP。')) {
                input.value = '';
                return;
            }
        }

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