// Absolute Axis - Private Cloud (NAS) Module
console.log("--- NAS MODULE V2.1 LOADED ---");
let currentNASPath = "";
let nasViewMode = 'grid';
let currentNASMode = 'drive';

function toggleNASView(mode) {
    nasViewMode = mode;
    const isLight = document.body.classList.contains('light-mode');
    const activeColor = isLight ? '#fff' : '#0d1117';
    
    document.getElementById('btn-grid').style.background = (mode==='grid'?'var(--accent-color)':'transparent');
    document.getElementById('btn-grid').style.color = (mode==='grid'?activeColor:'var(--text-main)');
    document.getElementById('btn-list').style.background = (mode==='list'?'var(--accent-color)':'transparent');
    document.getElementById('btn-list').style.color = (mode==='list'?activeColor:'var(--text-main)');
    
    loadNASFiles(currentNASPath);
}

function nasNav(m) {
    currentNASMode = m; currentNASPath = '';
    document.querySelectorAll('.nas-nav').forEach(e => e.classList.remove('active'));
    const navEl = document.getElementById('nas-nav-'+m);
    if(navEl) navEl.classList.add('active');
    loadNASFiles('');
}

async function loadNASFiles(path) {
    if(path && (currentNASMode === 'starred' || currentNASMode === 'recent')) {
        currentNASMode = 'drive';
        document.querySelectorAll('.nas-nav').forEach(e => e.classList.remove('active'));
        const driveNav = document.getElementById('nas-nav-drive');
        if(driveNav) driveNav.classList.add('active');
    }
    
    currentNASPath = path;
    const res = await authFetch(`/api/nas/list?path=${encodeURIComponent(path)}&mode=${currentNASMode}`);
    if(!res.ok) return;
    const data = await res.json();
    
    const bc = document.getElementById('nas-breadcrumb');
    const modeNames = {'drive':'我的雲端硬碟','shared':'與我共用','starred':'已加星號','recent':'近期存取','trash':'回收站'};
    bc.innerHTML = `<span style="color:var(--text-muted); cursor:pointer;" onclick="nasNav('${currentNASMode}')">${modeNames[currentNASMode]}</span>`;
    
    if(currentNASMode === 'drive') {
        const parts = path.split('/').filter(p=>p);
        let cum = '';
        parts.forEach((p, i) => {
            cum += (i===0?'':'/') + p;
            bc.innerHTML += ` <span style="color:var(--text-muted);">/</span> <span style="cursor:pointer;" onclick="loadNASFiles('${cum}')">${p}</span>`;
        });
    }

    const exp = document.getElementById('nas-explorer');
    exp.className = (nasViewMode==='grid'?'file-grid':'file-list');
    exp.innerHTML = data.files.length ? '' : '<div style="color:var(--text-muted); padding:2rem; width:100%; text-align:center;">此目錄為空</div>';
    
    data.files.forEach(f => {
        const icon = f.is_dir ? '📁' : (['.jpg','.png','.jpeg','.gif'].includes(f.ext)?'🖼️':(f.ext==='.pdf'?'📄':'📄'));
        const fullPath = (currentNASMode==='shared'?f.path:((currentNASPath?currentNASPath+'/':'')+f.name));
        const owner = f.owner || '';

        const item = document.createElement('div');
        if(nasViewMode === 'grid') {
            item.className = 'card file-card';
            const starIcon = f.starred ? '⭐' : '☆';
            item.onclick = f.is_dir ? () => loadNASFiles(fullPath) : () => previewFile(fullPath, f.ext, owner);
            item.oncontextmenu = (e) => showCM(e, fullPath, f.is_dir, f.ext, owner);
            item.innerHTML = `
                <div style="position:absolute; top:12px; left:12px; cursor:pointer; font-size:1.1rem;" onclick="event.stopPropagation(); toggleStar('${fullPath}')">${currentNASMode==='drive'?starIcon:''}</div>
                <div style="font-size:2rem; margin-bottom:12px;">${icon}</div>
                <div style="font-weight:700; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; width:100%; text-align:center; color:var(--text-main);">${f.name}</div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">${f.is_dir?'資料夾':(f.size/1024/1024).toFixed(1)+' MB'}</div>
            `;
        } else {
            item.className = 'file-list-item';
            const starIcon = f.starred ? '⭐' : '☆';
            item.onclick = f.is_dir ? () => loadNASFiles(fullPath) : () => previewFile(fullPath, f.ext, owner);
            item.oncontextmenu = (e) => showCM(e, fullPath, f.is_dir, f.ext, owner);
            item.innerHTML = `
                <div style="display:flex; align-items:center; gap:18px; flex:1; min-width:0;">
                    <span style="font-size:1.1rem; flex-shrink:0;" onclick="event.stopPropagation(); toggleStar('${fullPath}')">${currentNASMode==='drive'?starIcon:''}</span>
                    <div style="font-size:1.5rem; flex-shrink:0;">${icon}</div>
                    <div style="font-weight:700; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; color:var(--text-main);">${f.name}</div>
                </div>
                <div style="font-size:0.8rem; color:var(--text-muted); min-width:80px; text-align:right;">${f.is_dir?'資料夾':(f.size/1024/1024).toFixed(1)+' MB'}</div>
            `;
        }
        exp.appendChild(item);
    });

    const qP = (data.quota_used / data.quota_total * 100);
    const qBar = document.getElementById('quota-bar');
    if (qBar) qBar.style.width = qP + '%';
    const qLabel = document.getElementById('quota-label');
    if (qLabel) qLabel.innerText = `${(data.quota_used/1024/1024).toFixed(0)} MB / ${(data.quota_total/1024/1024).toFixed(0)} MB`;
}

// 檔案預覽修復的核心代碼
async function previewFile(path, ext, owner = '') {
    const url = `/api/nas/download?path=${encodeURIComponent(path)}${owner?'&owner='+encodeURIComponent(owner):''}`;
    const c = document.getElementById('preview-content');
    const n = document.getElementById('preview-filename');
    const modal = document.getElementById('modal-preview');
    
    if(!c || !n || !modal) {
        console.error("Preview modal components not found");
        return;
    }
    
    n.innerText = path.split('/').pop();
    c.innerHTML = '<div style="color:#fff; font-size:1.2rem;">🖼️ 正在加載預覽...</div>';
    modal.style.display = 'flex';

    try {
        const res = await authFetch(url);
        if(!res.ok) throw new Error("Load failed");
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const eTypes = (ext || "").toLowerCase();

        if(['.jpg', '.png', '.gif', '.webp', '.jpeg'].includes(eTypes)) {
            c.innerHTML = `<img src="${blobUrl}" style="max-width:100%; max-height:100%; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.5);">`;
        } else if(['.pdf'].includes(eTypes)) {
            c.innerHTML = `<iframe src="${blobUrl}" style="width:100%; height:100%; border:none; border-radius:12px;"></iframe>`;
        } else if(['.mp4', '.webm', '.ogg'].includes(eTypes)) {
            c.innerHTML = `<video controls autoplay src="${blobUrl}" style="max-width:100%; max-height:100%; border-radius:12px;"></video>`;
        } else if(['.txt', '.md', '.py', '.json', '.js', '.html', '.css'].includes(eTypes)) {
            const text = await blob.text();
            c.innerHTML = `<pre style="color:#fff; background:rgba(0,0,0,0.5); padding:30px; border-radius:12px; border:1px solid var(--border-color); width:100%; height:100%; overflow:auto; text-align:left; font-size:0.9rem; line-height:1.6;">${text.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>`;
        } else {
            c.innerHTML = `
                <div style="text-align:center;">
                    <div style="font-size:4rem; margin-bottom:20px;">📄</div>
                    <div style="color:var(--text-muted); margin-bottom:20px;">此檔案類型不支援線上預覽</div>
                    <button class="btn btn-primary" onclick="nasDL('${path}', '${owner}')">⬇️ 直接下載</button>
                </div>
            `;
        }
    } catch(e) {
        c.innerHTML = '<div style="color:var(--danger-color);">檔案載入失敗，請稍後再試</div>';
    }
}

function closePreview() {
    const modal = document.getElementById('modal-preview');
    const c = document.getElementById('preview-content');
    if (modal) modal.style.display = 'none';
    if (c) c.innerHTML = '';
}

// NAS Context Menu & Actions
let cmData = {path: '', isDir: false, ext: '', owner: ''};
function showCM(e, path, isDir, ext, owner = '') {
    console.log("Right click triggered on:", path);
    e.preventDefault(); e.stopPropagation();
    cmData = {path, isDir, ext, owner};
    const cm = document.getElementById('nas-context-menu');
    if (!cm) return;
    cm.style.display = 'block'; cm.style.left = e.clientX + 'px'; cm.style.top = e.clientY + 'px';
    
    document.getElementById('cm-share').style.display = (currentNASMode==='drive' && !isDir)?'flex':'none';
    document.getElementById('cm-star').style.display = (currentNASMode==='drive')?'flex':'none';
    document.getElementById('cm-restore').style.display = (currentNASMode==='trash')?'flex':'none';
    document.getElementById('cm-trash').style.display = (currentNASMode==='drive')?'flex':'none';
    document.getElementById('cm-del').style.display = (currentNASMode==='trash')?'flex':'none';
    document.getElementById('cm-dl').style.display = (isDir)?'none':'flex';
    document.getElementById('cm-open').innerText = isDir?'📂 開啟資料夾':'🔍 預覽檔案';
}

async function cmAction(act) {
    const p = cmData.path; const o = cmData.owner;
    document.getElementById('nas-context-menu').style.display = 'none';
    if(act==='open') { if(cmData.isDir) loadNASFiles(p); else previewFile(p, cmData.ext, o); }
    if(act==='dl') nasDL(p, o);
    if(act==='share') openShare(p);
    if(act==='star') toggleStar(p);
    if(act==='trash') nasToTrash(p);
    if(act==='restore') { await authFetch('/api/nas/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})}); loadNASFiles(''); }
    if(act==='delete') { if(confirm('永久刪除？不可恢復！')) { await authFetch('/api/nas/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})}); loadNASFiles(''); } }
}

async function toggleStar(p){ await authFetch('/api/nas/toggle_star',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})}); loadNASFiles(currentNASPath); }
async function nasToTrash(p){ await authFetch('/api/nas/trash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})}); loadNASFiles(currentNASPath); }

async function nasDL(p, owner = ''){
    const url = `/api/nas/download?path=${encodeURIComponent(p)}${owner?'&owner='+encodeURIComponent(owner):''}`;
    const r = await authFetch(url); 
    if(r.ok){
        const b=await r.blob(); 
        const u=URL.createObjectURL(b); 
        const a=document.createElement('a'); a.href=u; a.download=p.split('/').pop(); a.click();
    }
}

async function promptMkdir() {
    const name = prompt("請輸入資料夾名稱:");
    if(name) {
        const res = await authFetch('/api/nas/mkdir', {
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({path: currentNASPath, name: name})
        });
        if(res.ok) loadNASFiles(currentNASPath);
    }
}

async function openShare(p){
    const res = await authFetch('/api/nas/users');
    if(!res.ok) return alert("無法獲取使用者列表");
    const users = await res.json();
    const sel = document.getElementById('share-user-select');
    sel.innerHTML = users.map(u => `<option value="${u.username}">${u.username}</option>`).join('');
    document.getElementById('share-target-name').innerText = p.split('/').pop();
    document.getElementById('modal-share').setAttribute('data-path', p);
    document.getElementById('modal-share').style.display = 'flex';
}

async function confirmShare(){
    const p = document.getElementById('modal-share').getAttribute('data-path');
    const target = document.getElementById('share-user-select').value;
    if(!target) return alert('請選擇對象');
    await authFetch('/api/nas/share', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p, target_user:target})});
    document.getElementById('modal-share').style.display = 'none';
}

async function nasUpload() {
    const input = document.getElementById('nas-up');
    if(!input.files.length) return;
    const file = input.files[0];
    const mon = document.getElementById('upload-monitor');
    const bar = document.getElementById('up-bar');
    const speed = document.getElementById('up-speed');
    const name = document.getElementById('up-filename');

    mon.style.display = 'block';
    name.innerText = file.name;
    bar.style.width = '0%'; speed.innerText = '-- MB/s';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', currentNASPath);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/nas/upload', true);
    xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
    
    const startT = Date.now();
    xhr.upload.onprogress = (e) => {
        if(e.lengthComputable) {
            const pct = (e.loaded / e.total * 100).toFixed(1);
            bar.style.width = pct + '%';
            const dur = (Date.now() - startT) / 1000;
            if(dur > 0) speed.innerText = (e.loaded / 1024 / 1024 / dur).toFixed(1) + ' MB/s';
        }
    };
    xhr.onload = () => { setTimeout(() => { mon.style.display = 'none'; loadNASFiles(currentNASPath); }, 1000); };
    xhr.onerror = () => { alert('Upload failed!'); mon.style.display = 'none'; };
    xhr.send(formData);
}

// 點擊空白處隱藏選單
window.addEventListener('click', () => { 
    const cm = document.getElementById('nas-context-menu'); 
    if (cm) cm.style.display = 'none'; 
});