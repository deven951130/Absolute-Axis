// Absolute Axis - Virtualization (Docker/KVM) Module
// 容器名稱、映像名稱都用 textContent（dom.js 的 h()）；危險操作先用頁內 axisAsk() 確認。

function promptDeployVM(internalName, displayName) {
    document.getElementById('vm-os-internal').value = internalName;
    document.getElementById('deploy-vm-os').textContent = displayName;
    document.getElementById('vm-name').value = internalName + "_01";
    document.getElementById('modal-deploy-vm').style.display = 'flex';
}

async function confirmDeployVM() {
    const os = document.getElementById('vm-os-internal').value;
    const name = document.getElementById('vm-name').value;
    const cpu = parseInt(document.getElementById('vm-cpu').value);
    const ram = parseInt(document.getElementById('vm-ram').value);

    if (!name || name.includes(" ")) {
        toastText('名稱不能是空的，也不能有空白', 'warning');
        return;
    }

    document.getElementById('modal-deploy-vm').style.display = 'none';

    try {
        const res = await authFetch('/api/docker/deploy', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({os_internal_name: os, container_name: name, cpu_cores: cpu, ram_gb: ram})
        });
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
            toastText(d.message || '已開始部署', 'success');
            setTimeout(loadDocker, 2000);
        } else {
            toastText(d.message || d.detail || '部署失敗', 'error');
        }
    } catch (e) {
        toastText('請求失敗，請檢查網路', 'error');
    }
}

const _DOCKER_ACTIONS = {
    start: { label: '啟動' },
    restart: { label: '重新啟動' },
    stop: { label: '停止', ask: '停止後容器裡的服務會中斷。確定要停止嗎？', danger: false },
    'rm -f': { label: '移除', ask: '移除會刪除這個容器（強制，執行中的也會停掉），無法復原。確定要移除嗎？', danger: true },
};

async function controlDocker(id, act, name = '') {
    const spec = _DOCKER_ACTIONS[act];
    if (!spec) return;
    if (spec.ask) {
        const ok = await axisAsk({ title: `${spec.label}：${name || id}`, message: spec.ask, ok: spec.label, danger: spec.danger });
        if (!ok) return;
    }
    try {
        const res = await authFetch('/api/docker/control', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({container_id: id, action: act})
        });
        if (res.ok) toastText(`已送出：${spec.label} ${name || id}`, 'success');
        else if (res.status !== 401 && res.status !== 403) toastText(`${spec.label}失敗（HTTP ${res.status}）`, 'error');
    } catch (e) {
        toastText('請求失敗，請檢查網路', 'error');
    }
    setTimeout(loadDocker, 1000);
}

function openVNC(ip, port) {
    const p = parseInt(port, 10);
    if (!p || p < 1 || p > 65535) return;
    window.open(`http://${window.location.hostname}:${p}`, '_blank', 'noopener');
}

const _DOCKER_STATE = {
    running: '執行中', exited: '已停止', created: '已建立', paused: '已暫停',
    restarting: '重新啟動中', removing: '移除中', dead: '異常停止',
};

const _DOCKER_ICON = {
    heavy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M8 20h8M12 16v4"></path></svg>',
    app: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"></path><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"></path></svg>',
};

async function loadDocker() {
    const el = document.getElementById('docker-list');
    if (!el) return;
    const r = await authFetch('/api/docker/containers');
    if (!r.ok) return;
    const list = await r.json();

    if (!Array.isArray(list) || list.length === 0) {
        el.replaceChildren(h('p', { class: 'w-muted', style: 'margin: 0; padding: 18px 0; text-align: center;', text: '沒有容器。' }));
        return;
    }

    el.replaceChildren(...list.map((c) => {
        const up = String(c.State || '').toLowerCase() === 'running';
        const image = String(c.Image || '');
        const name = String(c.Names || c.ID || '');
        const isHeavyOS = ['dockurr', 'linuxserver', 'sickcodes', 'android'].some((k) => image.includes(k));

        const ico = h('span', { class: 'docker-ico', style: `background: ${isHeavyOS ? '#5E5CE6' : '#2E9BF0'};` });
        ico.innerHTML = isHeavyOS ? _DOCKER_ICON.heavy : _DOCKER_ICON.app;  // 固定的 SVG 常數

        const actions = h('div', { class: 'docker-actions' });
        if (up && isHeavyOS && c.vnc_port) {
            actions.append(h('button', { type: 'button', class: 'btn btn-primary', text: 'WebVNC 桌面',
                onclick: () => openVNC(window.location.hostname, c.vnc_port) }));
        } else if (up && isHeavyOS) {
            actions.append(h('span', { class: 'w-muted', style: 'font-size: 13px;', text: 'WebVNC 準備中…' }));
        }
        actions.append(
            up ? h('button', { type: 'button', class: 'btn btn-outline', text: '停止', onclick: () => controlDocker(c.ID, 'stop', name) })
               : h('button', { type: 'button', class: 'btn btn-primary', text: '啟動', onclick: () => controlDocker(c.ID, 'start', name) }),
            h('button', { type: 'button', class: 'btn btn-outline', text: '重新啟動', onclick: () => controlDocker(c.ID, 'restart', name) }),
            h('button', { type: 'button', class: 'btn btn-danger', text: '移除', onclick: () => controlDocker(c.ID, 'rm -f', name) }));

        return h('div', { class: 'docker-row' },
            ico,
            h('div', { class: 'docker-main' },
                h('div', { class: 'docker-name' }, h('span', { text: name }),
                    h('span', { class: `pill ${up ? 'ok' : ''}`, text: _DOCKER_STATE[String(c.State || '').toLowerCase()] || c.State || '未知' })),
                h('div', { class: 'docker-meta', text: `${image} · ${String(c.ID || '').slice(0, 12)}` })),
            actions);
    }));
}
