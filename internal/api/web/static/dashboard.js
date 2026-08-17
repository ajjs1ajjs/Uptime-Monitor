document.addEventListener('DOMContentLoaded', function() {
    const typeOrder = { 'http': 0, 'https': 1, 'ssl': 2, 'port': 3, 'ping': 4 };
    const filters = document.getElementById('monitorFilters');
    if (filters) {
        const types = [...new Set((sitesData || []).map(s => s.monitor_type || 'http').filter(Boolean))];
        types.sort((a,b) => (typeOrder[a] ?? 99) - (typeOrder[b] ?? 99));
        types.forEach(t => {
            const btn = document.createElement('button');
            btn.className = 'px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:border-accent hover:text-white transition text-xs font-medium';
            btn.textContent = t.toUpperCase();
            btn.dataset.filter = t;
            btn.onclick = () => setFilter(t);
            filters.appendChild(btn);
        });
    }
});

var notifyConfig = {};
try { var __nc = document.getElementById('notify-config');
  if (__nc) notifyConfig = JSON.parse(__nc.textContent || '{}'); } catch (e) { notifyConfig = {}; }
let currentFilter = 'all';

// escHtml escapes a value for safe insertion into innerHTML strings.
function escHtml(v) {
    if (v === null || v === undefined) return '';
    const d = document.createElement('div');
    d.textContent = String(v);
    return d.innerHTML;
}

// jsAttr escapes a value for use inside a double-quoted HTML attribute.
function jsAttr(v) {
    return escHtml(v).replace(/"/g, '&quot;');
}

function renderNotifyChannelOptions(containerId, selectedChannels) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const selected = selectedChannels || [];
    const methodIcons = {telegram:'📱', discord:'🎮', teams:'🏢', email:'📧', slack:'💬', sms:'📱', webhook:'🔗', pushover:'📲', gotify:'🔔', ntfy:'📡'};
    const methodNames = {telegram:'Telegram', discord:'Discord', teams:'MS Teams', email:'Email', slack:'Slack', sms:'SMS', webhook:'Webhook', pushover:'Pushover', gotify:'Gotify', ntfy:'Ntfy'};
    let html = '';
    for (const [method, config] of Object.entries(notifyConfig)) {
        if (!config.enabled) continue;
        const channels = config.channels || [];
        if (channels.length === 0) continue;
        const icon = methodIcons[method] || '🔔';
        const name = methodNames[method] || method;
        html += `<div class="mb-1.5">
            <div class="text-[11px] font-semibold text-slate-500 mb-1 uppercase tracking-wider">${icon} ${name}</div>
            <div class="flex flex-wrap gap-1.5">`;
        channels.forEach(ch => {
            const chId = ch.id || '';
            const chName = ch.name || chId;
            const checked = selected.includes(chId);
            const cls = checked
                ? 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent/10 border border-accent/40 cursor-pointer hover:border-accent transition text-xs'
                : 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 cursor-pointer hover:border-accent transition text-xs';
            html += `<label class="${cls}">
                <input type="checkbox" value="${jsAttr(chId)}" data-method="${jsAttr(method)}" class="accent-accent w-3 h-3" ${checked ? 'checked' : ''}> ${escHtml(chName)}
            </label>`;
        });
        html += `</div></div>`;
    }
    container.innerHTML = html || '<div class="text-xs text-slate-500 py-2">Спочатку налаштуйте канали в розділі Налаштування</div>';
    container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', function() {
            const lbl = this.closest('label');
            if (this.checked) {
                lbl.className = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent/10 border border-accent/40 cursor-pointer hover:border-accent transition text-xs';
            } else {
                lbl.className = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 cursor-pointer hover:border-accent transition text-xs';
            }
        });
    });
}

function getSelectedNotifyMethods(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];
    const methodMap = {};
    container.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
        const method = cb.dataset.method;
        const chId = cb.value;
        if (!methodMap[method]) methodMap[method] = [];
        if (!methodMap[method].includes(chId)) methodMap[method].push(chId);
    });
    return Object.entries(methodMap).map(([method, channels]) => ({method, channels}));
}

function channelIdsFromMethods(methods) {
    if (!Array.isArray(methods)) return [];
    const ids = new Set();
    methods.forEach(item => {
        if (typeof item === 'string') {
            const config = notifyConfig[item];
            if (config && config.enabled && config.channels) {
                config.channels.forEach(ch => { if (ch.id) ids.add(ch.id); });
            }
        } else if (typeof item === 'object' && item !== null) {
            (item.channels || []).forEach(id => ids.add(id));
        }
    });
    return [...ids];
}

function toggleKeywordField(selectId, containerId) {
    const select = document.getElementById(selectId);
    const container = document.getElementById(containerId);
    if (select && container) {
        container.style.display = select.value === 'http' ? 'block' : 'none';
        if (select.value !== 'http') {
            const input = container.querySelector('input');
            if (input) input.value = '';
        }
    }
}
let sitesData = [];
let sslCertificatesData = [];
let gaugeCharts = {};
let responseTimeData = [];
let incidentsData = [];
let incidentsRefreshInterval = null;
let currentTagFilter = 'all';

function setTagFilter(tag) {
    currentTagFilter = tag;
    document.querySelectorAll('#tagFilters button').forEach(b => {
        const active = b.dataset.tag === tag;
        b.className = active 
            ? 'tag-filter-btn px-3 py-1.5 rounded-lg bg-accent/20 border border-accent text-accent font-medium text-xs transition'
            : 'tag-filter-btn px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:border-accent hover:text-white transition text-xs font-medium';
    });
    renderMonitors();
}

function updateTagFilters() {
    const container = document.getElementById('tagFilters');
    if (!container) return;
    
    const allTags = new Set();
    sitesData.forEach(s => {
        const tags = Array.isArray(s.tags) ? s.tags : [];
        tags.forEach(t => allTags.add(t));
    });
    
    const existing = container.querySelectorAll('button[data-tag]');
    existing.forEach(b => {
        if (b.dataset.tag !== 'all') b.remove();
    });
    
    const sortedTags = Array.from(allTags).sort();
    sortedTags.forEach(t => {
        const btn = document.createElement('button');
        btn.dataset.tag = t;
        btn.textContent = t;
        btn.onclick = () => setTagFilter(t);
        if (t === currentTagFilter) {
            btn.className = 'tag-filter-btn px-3 py-1.5 rounded-lg bg-accent/20 border border-accent text-accent font-medium text-xs transition';
        } else {
            btn.className = 'tag-filter-btn px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:border-accent hover:text-white transition text-xs font-medium';
        }
        container.appendChild(btn);
    });
    
    if (currentTagFilter !== 'all' && !allTags.has(currentTagFilter)) {
        setTagFilter('all');
    }
}

let selectedAddTags = [];
let selectedEditTags = [];

function toggleTagSelection(type, tag) {
    const list = type === 'add' ? selectedAddTags : selectedEditTags;
    const idx = list.indexOf(tag);
    if (idx === -1) {
        list.push(tag);
    } else {
        list.splice(idx, 1);
    }
    renderTagsWidget(type);
    updateExistingTagsSuggest(type === 'add' ? 'existingTagsContainer' : 'editExistingTagsContainer', type === 'add' ? 'siteTagsInput' : 'editSiteTagsInput', type);
}

function renderTagsWidget(type) {
    const widgetId = type === 'add' ? 'siteTagsWidget' : 'editSiteTagsWidget';
    const inputId = type === 'add' ? 'siteTagsInput' : 'editSiteTagsInput';
    const widget = document.getElementById(widgetId);
    const input = document.getElementById(inputId);
    if (!widget || !input) return;
    
    widget.querySelectorAll('.tag-chip').forEach(c => c.remove());
    
    const list = type === 'add' ? selectedAddTags : selectedEditTags;
    list.forEach(t => {
        const chip = document.createElement('span');
        chip.className = 'tag-chip inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-accent/15 border border-accent/30 text-accent text-xs font-semibold';
        chip.innerHTML = `📁 ${escHtml(t)} <button class="hover:text-white transition font-bold focus:outline-none ml-1 text-sm leading-none" data-action="removeTagChip" data-type="${type}" data-tag="${jsAttr(t)}">&times;</button>`;
        widget.insertBefore(chip, input);
    });
    
    if (list.length > 0) {
        input.placeholder = '';
    } else {
        input.placeholder = 'Додати папку...';
    }
}

function removeTagChip(type, tag) {
    const list = type === 'add' ? selectedAddTags : selectedEditTags;
    const idx = list.indexOf(tag);
    if (idx !== -1) {
        list.splice(idx, 1);
        renderTagsWidget(type);
        updateExistingTagsSuggest(type === 'add' ? 'existingTagsContainer' : 'editExistingTagsContainer', type === 'add' ? 'siteTagsInput' : 'editSiteTagsInput', type);
    }
}

function setupTagsEventListeners() {
    ['add', 'edit'].forEach(type => {
        const inputId = type === 'add' ? 'siteTagsInput' : 'editSiteTagsInput';
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                const val = input.value.trim().replace(/,/g, '');
                if (val) {
                    const list = type === 'add' ? selectedAddTags : selectedEditTags;
                    if (!list.includes(val)) {
                        list.push(val);
                    }
                    input.value = '';
                    renderTagsWidget(type);
                    updateExistingTagsSuggest(type === 'add' ? 'existingTagsContainer' : 'editExistingTagsContainer', inputId, type);
                }
            } else if (e.key === 'Backspace' && !input.value) {
                const list = type === 'add' ? selectedAddTags : selectedEditTags;
                if (list.length > 0) {
                    list.pop();
                    renderTagsWidget(type);
                    updateExistingTagsSuggest(type === 'add' ? 'existingTagsContainer' : 'editExistingTagsContainer', inputId, type);
                }
            }
        });
    });
}

function updateExistingTagsSuggest(containerId, inputId, type = 'add') {
    const container = document.getElementById(containerId);
    const input = document.getElementById(inputId);
    if (!container || !input) return;
    
    const allTags = new Set();
    sitesData.forEach(s => {
        const tags = Array.isArray(s.tags) ? s.tags : [];
        tags.forEach(t => allTags.add(t));
    });
    
    container.innerHTML = '';
    if (allTags.size > 0) {
        const label = document.createElement('span');
        label.className = 'text-xs text-slate-500 self-center mr-1';
        label.textContent = 'Вибрати існуючу:';
        container.appendChild(label);
        
        const currentList = type === 'add' ? selectedAddTags : selectedEditTags;
        allTags.forEach(t => {
            const span = document.createElement('span');
            const isSelected = currentList.includes(t);
            if (isSelected) {
                span.className = 'px-2 py-1 bg-accent/20 border border-accent rounded-lg text-xs text-accent font-semibold cursor-pointer transition flex items-center gap-1';
                span.textContent = `✓ ${t}`;
            } else {
                span.className = 'px-2 py-1 bg-slate-800/70 border border-slate-700/50 rounded-lg text-xs text-slate-300 cursor-pointer hover:border-accent hover:text-white transition';
                span.textContent = t;
            }
            span.onclick = (e) => {
                e.stopPropagation();
                toggleTagSelection(type, t);
            };
            container.appendChild(span);
        });
    }
}

function setFilter(type) {
    currentFilter = type;
    document.querySelectorAll('#monitorFilters button').forEach(b => {
        b.classList.toggle('bg-accent/20', b.dataset.filter === type);
        b.classList.toggle('text-accent', b.dataset.filter === type);
        b.classList.toggle('text-slate-400', b.dataset.filter !== type);
    });
    renderMonitors();
}

async function loadSites() {
    try {
        const resp = await fetch('/api/sites');
        sitesData = await resp.json();
        renderMonitors();
        updateStats();
        updateGauges();
        updateTagFilters();
        updateExistingTagsSuggest('existingTagsContainer', 'siteTagsInput', 'add');
        updateExistingTagsSuggest('editExistingTagsContainer', 'editSiteTagsInput', 'edit');

        // Update filters
        const filters = document.querySelector('#monitorFilters');
        if (filters) {
            const types = [...new Set(sitesData.map(s => s.monitor_type || 'http').filter(Boolean))];
            types.sort((a,b) => (['http','https','ssl','port','ping'].indexOf(a)+1 || 99) - (['http','https','ssl','port','ping'].indexOf(b)+1 || 99));
            const existing = filters.querySelectorAll('button[data-filter]');
            existing.forEach(b => {
                if (b.dataset.filter !== 'all') b.remove();
            });
            types.forEach(t => {
                if (!filters.querySelector(`[data-filter="${t}"]`)) {
                    const btn = document.createElement('button');
                    btn.className = 'px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:border-accent hover:text-white transition text-xs font-medium';
                    btn.dataset.filter = t;
                    btn.textContent = t.toUpperCase();
                    btn.onclick = () => setFilter(t);
                    filters.appendChild(btn);
                }
            });
        }
    } catch(e) { console.error(e); }
}

function updateStats() {
    const up = sitesData.filter(s => s.status === 'up').length;
    const down = sitesData.filter(s => s.status === 'down').length;
    const total = sitesData.length;
    const totalEl = document.getElementById('totalSites');
    if (totalEl) totalEl.textContent = total;
    const upEl = document.getElementById('upSites');
    if (upEl) upEl.textContent = up;
    const downEl = document.getElementById('downSites');
    if (downEl) downEl.textContent = down;
    const lastUpdateEl = document.getElementById('lastUpdate');
    if (lastUpdateEl) lastUpdateEl.textContent = 'Updated: ' + new Date().toLocaleTimeString();
}

function createGaugeChart(canvasId, value, color) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'doughnut',
        data: { datasets: [{ data: [value, 100 - value], backgroundColor: [color, 'rgba(255,255,255,0.1)'], borderWidth: 0, circumference: 180, rotation: 270 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { tooltip: { enabled: false }, legend: { display: false } } }
    });
}

function updateGauges() {
    const up = sitesData.filter(s => s.status === 'up').length;
    const total = sitesData.length || 1;
    const uptimePercent = Math.round((up / total) * 100);
    const responseTimes = sitesData.filter(s => s.response_time).map(s => s.response_time);
    const avgResponse = responseTimes.length ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length) : 0;
    const sslExpiring = (sslCertificatesData || []).filter(s => s.days_until_expire <= 7).length || 0;

    document.getElementById('uptimeValue').textContent = uptimePercent + '%';
    document.getElementById('responseValue').textContent = avgResponse + 'ms';
    document.getElementById('sslValue').textContent = sslExpiring > 0 ? '⚠️ ' + sslExpiring : '✅ OK';

    const uptimeColor = uptimePercent >= 99 ? '#10b981' : uptimePercent >= 95 ? '#f59e0b' : '#ef4444';
    const responseColor = avgResponse <= 200 ? '#10b981' : avgResponse <= 500 ? '#f59e0b' : '#ef4444';
    const sslColor = sslExpiring === 0 ? '#10b981' : '#f59e0b';

    // Destroy existing charts before recreating to prevent memory leaks
    Object.values(gaugeCharts).forEach(c => { try { c.destroy(); } catch {} });
    gaugeCharts.uptime = createGaugeChart('uptimeGauge', uptimePercent, uptimeColor);
    gaugeCharts.response = createGaugeChart('responseGauge', Math.min(avgResponse / 5, 100), responseColor);
    gaugeCharts.ssl = createGaugeChart('sslGauge', sslExpiring === 0 ? 100 : 50, sslColor);
}



function renderMonitors() {
    const grid = document.getElementById('monitorsGrid');
    if (!grid) return;
    
    const searchQuery = (document.getElementById('monitorSearch')?.value || '').toLowerCase().trim();
    const sortVal = document.getElementById('monitorSort')?.value || 'status';
    
    let filtered = currentFilter === 'all' ? sitesData : sitesData.filter(s => s.monitor_type === currentFilter);
    
    if (currentTagFilter !== 'all') {
        filtered = filtered.filter(s => {
            const tags = Array.isArray(s.tags) ? s.tags : [];
            return tags.includes(currentTagFilter);
        });
    }
    
    if (searchQuery) {
        filtered = filtered.filter(s => 
            (s.name || '').toLowerCase().includes(searchQuery) || 
            (s.url || '').toLowerCase().includes(searchQuery)
        );
    }
    
    if (sortVal === 'name') {
        filtered.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    } else if (sortVal === 'uptime') {
        filtered.sort((a, b) => (b.uptime ?? 100) - (a.uptime ?? 100));
    } else if (sortVal === 'response_time') {
        filtered.sort((a, b) => {
            const rtA = a.response_time ?? 999999;
            const rtB = b.response_time ?? 999999;
            return rtA - rtB;
        });
    } else {
        // status
        filtered.sort((a, b) => {
            const o = {down:0, slow:1, maintenance:2, paused:3, unknown:4, up:5};
            return (o[a.status]??6) - (o[b.status]??6);
        });
    }
    
    if (filtered.length === 0) { grid.innerHTML = '<div class="col-span-full text-center py-10 text-slate-500">No monitors found.</div>'; return; }
    
    const lang = localStorage.getItem('lang') || 'uk';
    const dict = i18n[lang] || i18n.uk;

    let html = '';
    filtered.forEach(site => {
        let statusClass = 'down';
        let statusColor = '#ef4444';
        let statusText = 'DOWN';
        if (site.status === 'up') {
            statusClass = 'up';
            statusColor = '#10b981';
            statusText = 'UP';
        } else if (site.status === 'paused') {
            statusClass = 'paused';
            statusColor = '#f59e0b';
            statusText = 'PAUSED';
        } else if (site.status === 'maintenance') {
            statusClass = 'maintenance';
            statusColor = '#a855f7';
            statusText = 'MAINTENANCE';
        }
        
        const esc = v => { const d = document.createElement('div'); d.textContent = v || ''; return d.innerHTML; };
        const jsStr = v => (v || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeName = esc(site.name);
        const safeUrl = esc(site.url);
        const methods = Array.isArray(site.notify_methods) ? site.notify_methods : [];
        const monitorType = site.monitor_type || 'http';
        const safeKeyword = esc(site.keyword);
        const keywordHtml = site.keyword ? `<div class="text-[11px] text-indigo-400 mt-1 flex items-center gap-1">🔑 Ключ: <span class="text-slate-300 font-mono">${esc(site.keyword)}</span></div>` : '';

        const tags = Array.isArray(site.tags) ? site.tags : [];
        let tagsHtml = '';
        if (tags.length > 0) {
            tagsHtml = `<div class="flex gap-1 mt-1 flex-wrap">` +
                tags.slice(0, 3).map(tag => `<span class="px-2 py-0.5 bg-slate-700/50 rounded-full text-[10px] text-slate-400">📁 ${esc(tag)}</span>`).join('') +
                `</div>`;
        }
        const safeTags = encodeURIComponent(JSON.stringify(tags));

        let borderClass = 'border-red-500';
        if (statusClass === 'up') borderClass = 'border-emerald-500';
        else if (statusClass === 'paused') borderClass = 'border-amber-500';
        else if (statusClass === 'maintenance') borderClass = 'border-purple-500';

        html += `<div class="monitor-card gradient-card rounded-xl p-5 border-l-4 ${borderClass} border border-slate-700/30 card-hover transition" data-site-id="${site.id}">
            <div class="monitor-card-header flex justify-between items-start mb-4">
                <div class="min-w-0 flex-1">
                    <div class="text-base font-semibold truncate" title="${safeName}">${safeName}</div>
                    <a href="${esc(site.url)}" target="_blank" class="text-xs text-slate-400 hover:text-accent hover:underline truncate mt-0.5 block" title="${safeUrl}">${safeUrl}</a>
                    ${keywordHtml}
                    ${tagsHtml}
                    ${statusClass === 'down' && site.error_message ? `<div class="text-[11px] text-red-400 mt-1 truncate" title="${esc(site.error_message)}">⚠️ ${esc(site.error_message)}</div>` : ''}
                                    </div>
                <span class="px-3 py-1 rounded-full text-[10px] font-bold uppercase bg-accent/10 text-accent">${esc(monitorType)}</span>
            </div>
            <div class="monitor-card-metrics grid grid-cols-4 gap-2 py-3 border-y border-slate-700/30 text-center text-xs">
                <div><div class="text-sm font-bold status-badge ${statusClass}" style="color:${statusColor}">${statusText}</div><div class="text-slate-500 mt-0.5">${dict.card_status || 'Status'}</div></div>
                <div><div class="text-sm font-bold text-slate-200 response-time">${site.response_time || '—'}ms</div><div class="text-slate-500 mt-0.5">${dict.card_time || 'Time'}</div></div>
                <div><div class="text-sm font-bold text-slate-200">${(site.uptime || 100).toFixed(1)}%</div><div class="text-slate-500 mt-0.5">${dict.card_uptime || 'Uptime'}</div></div>
                <div><div class="text-sm font-bold text-slate-200">${site.status_code || '—'}</div><div class="text-slate-500 mt-0.5">${dict.card_http || 'HTTP'}</div></div>
            </div>
            <div class="monitor-card-actions flex gap-2 mt-4">
                <button data-action="checkSite" data-id="${site.id}" class="flex-1 py-2.5 rounded-lg gradient-accent text-black text-xs font-bold hover:shadow-lg hover:shadow-cyan-500/30 transition">${dict.card_check || '🔄 Check'}</button>
                <button data-action="openEditModal" data-id="${site.id}" data-name="${esc(site.name)}" data-url="${encodeURIComponent(site.url)}" data-methods="${encodeURIComponent(JSON.stringify(methods))}" data-interval="${site.check_interval||60}" data-timeout="${site.request_timeout_seconds||30}" data-retry-interval="${site.retry_interval_seconds||20}" data-max-retries="${site.max_retries ?? 3}" data-up-threshold="${site.up_success_threshold||2}" data-mtype="${monitorType}" data-keyword="${encodeURIComponent(site.keyword||'')}" data-tags="${safeTags}" class="flex-1 py-2.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition text-xs font-medium">${dict.card_edit || '✏️ Edit'}</button>
                <button data-action="deleteSite" data-id="${site.id}" class="flex-1 py-2.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition text-xs font-medium">${dict.card_delete || '🗑️ Delete'}</button>
            </div>
        </div>`;
    });
    grid.innerHTML = html;
}

async function checkSite(id) { try { await fetch('/api/sites/' + id + '/check', {method:'POST'}); loadSites(); } catch(e) { console.error(e); } }
async function deleteSite(id) { if (!confirm('Видалити цей монітор?')) return; try { await fetch('/api/sites/' + id, {method:'DELETE'}); loadSites(); } catch(e) { console.error(e); } }

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(b => { b.classList.remove('bg-accent', 'text-black'); b.classList.add('text-slate-400'); });
    document.getElementById('tab-' + tabId).classList.remove('hidden');
    document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('bg-accent', 'text-black');
    if (tabId === 'dashboard') { loadSites(); loadResponseTimeChart(); loadSSLTimelineChart(); renderDashboardIncidents(); }
    if (tabId === 'monitors') { loadSites(); }
    if (tabId === 'ssl') loadSSLCertificates();
    if (tabId === 'incidents') loadIncidents();
    if (tabId === 'maintenance') loadMaintenanceWindows();
    if (tabId === 'notifications') loadNotificationsHistory();
    if (tabId === 'settings') { loadAppSettings(); loadAlertPolicy(); }
}

async function loadNotificationsHistory() {
    const tbody = document.getElementById('notificationHistoryList');
    if (!tbody) return;
    try {
        const resp = await fetch('/api/notification-history');
        const data = await resp.json();
        if (!Array.isArray(data) || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="py-10 text-center text-slate-500">Ще не було сповіщень.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(n => {
            const methodIcons = {telegram:'📱', discord:'🎮', teams:'🏢', email:'📧', slack:'💬', sms:'📱', webhook:'🔗', pushover:'📲', gotify:'🔔', ntfy:'📡'};
            const icon = methodIcons[n.method] || '🔔';
            const time = (n.sent_at || '').substring(0, 19).replace('T', ' ');
            const statusClass = n.status === 'sent' ? 'text-emerald-400' : 'text-red-400';
            const preview = (n.message_preview || '').substring(0, 80);
            return `<tr class="hover:bg-slate-800/30 transition">
                <td class="py-3 px-4 text-xs text-slate-400">${escHtml(time)}</td>
                <td class="py-3 px-4 text-sm">${escHtml(n.site_name)}</td>
                <td class="py-3 px-4 text-sm">${icon} ${escHtml(n.method)}</td>
                <td class="py-3 px-4 text-sm ${statusClass}">${escHtml(n.status)}</td>
                <td class="py-3 px-4 text-xs text-slate-400 max-w-xs truncate">${escHtml(preview)}</td>
            </tr>`;
        }).join('');
    } catch(e) { console.error(e); tbody.innerHTML = '<tr><td colspan="5" class="py-10 text-center text-red-400">Помилка завантаження</td></tr>'; }
}

async function addSite() {
    const name = document.getElementById('siteName').value;
    const url = document.getElementById('siteUrl').value;
    const monitor_type = document.getElementById('monitorType').value;
    const keyword = document.getElementById('siteKeyword').value;
    const tags = selectedAddTags;
    const check_interval = parseInt(document.getElementById('siteCheckInterval').value) || 60;
    const notify_methods = getSelectedNotifyMethods('siteNotifyOptions');
    if (!name || !url) return alert('Заповніть назву та URL');
    try {
        const resp = await fetch('/api/sites', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, url, monitor_type, check_interval, notify_methods, keyword, tags})});
        if (resp.ok) {
            document.getElementById('siteName').value = '';
            document.getElementById('siteUrl').value = '';
            document.getElementById('siteKeyword').value = '';
            selectedAddTags = [];
            renderTagsWidget('add');
            loadSites();
            alert('Монітор додано!');
        }
    } catch(e) { console.error(e); }
}

async function loadSSLCertificates() {
    try { const resp = await fetch('/api/ssl-certificates'); sslCertificatesData = await resp.json(); renderSSLCertificates(); } catch(e) { console.error(e); }
}
function renderSSLCertificates() {
    const grid = document.getElementById('sslGrid');
    if (!grid) return;
    if (sslCertificatesData.length === 0) { grid.innerHTML = '<div class="col-span-full text-center py-10 text-slate-500">No SSL data.</div>'; return; }
    let html = '';
    sslCertificatesData.forEach(cert => {
        const days = cert.days_until_expire;
        const statusColor = days <= 0 ? '#ef4444' : days <= 7 ? '#f59e0b' : '#10b981';
        html += `<div class="rounded-xl p-4 border-l-4" style="border-left-color:${statusColor};background:rgba(30,41,59,0.4);border:1px solid rgba(148,163,184,0.1);">
            <div class="font-semibold text-sm truncate" title="${escHtml(cert.site_name)}">${escHtml(cert.site_name)}</div>
            <div class="text-xs text-slate-400 truncate mb-2" title="${escHtml(cert.hostname)}">${escHtml(cert.hostname)}</div>
            <div class="flex justify-between text-xs"><span>Term: ${days} days</span><span style="color:${statusColor}">${days <= 0 ? '❌ Overdue' : '✅ Valid'}</span></div>
        </div>`;
    });
    grid.innerHTML = html;
}

async function loadDashboard() { loadSites(); loadSSLCertificates(); await loadResponseTimeChart(); await loadSSLTimelineChart(); await loadIncidents(); }

async function loadResponseTimeChart() {
    try {
        const resp = await fetch('/api/stats/response-time');
        const data = await resp.json();
        const canvas = document.getElementById('responseTimeChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (window._respChart) window._respChart.destroy();
        if (!data || data.length === 0) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#6b7280'; ctx.font = '14px Inter'; ctx.textAlign = 'center';
            ctx.fillText('No response time data yet', canvas.width/2, canvas.height/2);
            return;
        }
        window._respChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.site_name?.length > 12 ? d.site_name.substring(0,12)+'…' : d.site_name),
                datasets: [
                    { label: 'Середній (мс)', data: data.map(d => d.avg_time || 0), backgroundColor: '#00d9ff', borderRadius: 4 },
                    { label: 'Макс (мс)', data: data.map(d => d.max_time || 0), backgroundColor: 'rgba(239,68,68,0.6)', borderRadius: 4 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#94a3b8' } } },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                    y: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } }
                }
            }
        });
    } catch(e) { console.error(e); }
}

async function loadSSLTimelineChart() {
    try {
        const resp = await fetch('/api/ssl-certificates');
        const certs = await resp.json();
        const canvas = document.getElementById('sslTimelineChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (window._sslChart) window._sslChart.destroy();
        if (!certs || certs.length === 0) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#6b7280'; ctx.font = '14px Inter'; ctx.textAlign = 'center';
            ctx.fillText('No SSL data yet', canvas.width/2, canvas.height/2);
            return;
        }
        const labels = certs.map(c => c.site_name?.length > 15 ? c.site_name.substring(0,15)+'…' : c.site_name);
        const days = certs.map(c => c.days_until_expire || 0);
        const colors = days.map(d => d <= 0 ? '#ef4444' : d <= 7 ? '#f59e0b' : d <= 30 ? '#00d9ff' : '#10b981');

        window._sslChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{ label: 'Днів до завершення', data: days, backgroundColor: colors, borderRadius: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { display: false } }
                }
            }
        });
    } catch(e) { console.error(e); }
}

async function loadIncidents() {
    try { const resp = await fetch('/api/incidents'); incidentsData = await resp.json(); renderIncidents(); renderDashboardIncidents(); const icEl = document.getElementById('incidentCount'); if (icEl) icEl.textContent = incidentsData.length; } catch(e) { console.error(e); }
}
function renderIncidents() {
    const list = document.getElementById('incidentsList');
    if (!list) return;
    if (incidentsData.length === 0) { list.innerHTML = '<div class="text-center py-10 text-slate-500">No incidents.</div>'; return; }
    list.innerHTML = '<div class="space-y-3">' + incidentsData.map(inc => {
        const isDown = inc.status === 'down';
        const bgColor = isDown ? 'rgba(239,68,68,0.1)' : 'rgba(234,179,8,0.1)';
        const borderColor = isDown ? '#ef4444' : '#eab308';
        const statusText = isDown ? '🔴 DOWN' : '🟡 SLOW';
        const date = inc.checked_at ? new Date(inc.checked_at).toLocaleString('uk-UA') : '';
        return `<div style="background:${bgColor};border-left:4px solid ${borderColor}" class="p-4 rounded-xl">
            <div class="flex items-center gap-2 mb-1"><span class="font-semibold text-sm">${escHtml(inc.site_name)}</span><span class="text-xs px-2 py-0.5 rounded" style="background:${borderColor}22;color:${borderColor}">${statusText}</span></div>
            <div class="text-xs text-slate-400">${escHtml(inc.site_url)}</div>
            ${inc.duration ? `<div class="text-xs mt-1" style="color:${borderColor}">⏱️ Duration: ${escHtml(inc.duration)}</div>` : ''}
            <div class="text-xs text-slate-500 mt-1">🕐 ${date}${inc.response_time ? ' ⚡ '+Math.round(inc.response_time)+'ms' : ''}${inc.status_code ? ' 📄 HTTP '+inc.status_code : ''}</div>
            ${inc.error_message ? `<div class="text-xs text-red-400 mt-2 p-2 bg-black/20 rounded font-mono">${escHtml(inc.error_message)}</div>` : ''}
        </div>`;
    }).join('') + '</div>';
}
async function checkAllMonitors() { for (const site of sitesData) { try { await fetch('/api/sites/' + site.id + '/check', {method:'POST'}); } catch(e) {} } loadSites(); }
async function checkSSLCertificates() { try { await fetch('/api/ssl-certificates/check', {method:'POST'}); loadSSLCertificates(); } catch(e) { console.error(e); } }
function renderDashboardIncidents() {
    const container = document.getElementById('dashboardIncidents');
    if (!container) return;
    if (!incidentsData || incidentsData.length === 0) {
        container.innerHTML = '<div class="text-center py-6 text-slate-500">✅ Немає інцидентів — всі монітори працюють!</div>';
        return;
    }
    const recent = incidentsData.slice(0, 5);
    container.innerHTML = recent.map(inc => {
        const isDown = inc.status === 'down';
        const borderColor = isDown ? '#ef4444' : '#eab308';
        const statusText = isDown ? '🔴 DOWN' : '🟡 SLOW';
        const date = inc.checked_at ? new Date(inc.checked_at).toLocaleString('uk-UA') : '';
        return `<div style="border-left:3px solid ${borderColor}" class="pl-3 py-2 border-b border-slate-700/20 last:border-0">
            <div class="flex items-center gap-2 text-sm"><span class="font-medium truncate">${escHtml(inc.site_name)}</span><span class="text-[10px] px-1.5 py-0.5 rounded" style="background:${borderColor}22;color:${borderColor}">${statusText}</span></div>
            <div class="text-xs text-slate-500 mt-0.5">🕐 ${date}${inc.response_time ? ' ⚡'+Math.round(inc.response_time)+'ms' : ''}</div>
        </div>`;
    }).join('');
}

// Notifications
function initNotifyUI() {
    ['telegram','teams','discord','slack','email','sms','webhook'].forEach(method => {
        const config = notifyConfig[method] || {};
        const toggle = document.getElementById('toggle-' + method);
        if (toggle && config.enabled) toggle.checked = true;
    });
}
function toggleNotify(method) {
    const card = document.getElementById('card-' + method);
    const toggle = document.getElementById('toggle-' + method);
    if (card && toggle) card.style.borderColor = toggle.checked ? 'rgba(16,185,129,0.4)' : 'rgba(148,163,184,0.1)';
}
function updateChannelFields() {
    const m = document.getElementById('addChannelMethod').value;
    document.getElementById('telegramFields').style.display = m === 'telegram' ? 'block' : 'none';
    document.getElementById('webhookFields').style.display = (m !== 'telegram' && m !== 'email') ? 'block' : 'none';
    document.getElementById('emailFields').style.display = m === 'email' ? 'block' : 'none';
}
function openAddChannelModal(method) {
    document.getElementById('addChannelMethod').value = method;
    document.getElementById('newChannelName').value = '';
    ['newTelegramToken','newTelegramChatId','newTelegramThreadId','newWebhookUrl','newEmailSmtp','newEmailPort','newEmailUser','newEmailPass','newEmailTo'].forEach(id => document.getElementById(id).value = '');
    updateChannelFields();
    document.getElementById('addChannelModal').classList.remove('hidden');
    document.getElementById('addChannelModal').classList.add('flex');
}
function closeAddChannelModal() { document.getElementById('addChannelModal').classList.add('hidden'); document.getElementById('addChannelModal').classList.remove('flex'); }
function addNewChannel() {
    const method = document.getElementById('addChannelMethod').value;
    const name = document.getElementById('newChannelName').value.trim();
    if (!name) return alert('Введіть назву каналу!');
    const channelId = 'ch_' + Date.now();
    const container = document.getElementById('channels-' + method);
    if (!container) return;
    let html = '';
    if (method === 'telegram') {
        const token = document.getElementById('newTelegramToken').value.trim();
        const chat_id = document.getElementById('newTelegramChatId').value.trim();
        const message_thread_id = document.getElementById('newTelegramThreadId').value.trim();
        if (!token || !chat_id) return alert('Введіть токен та chat_id!');
        __secrets[channelId] = { token, chat_id, message_thread_id };
        html = `<div class="channel-item p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 mb-2" id="ch_${channelId}">
            <div class="flex justify-between items-center"><span class="text-sm font-medium">📱 ${escHtml(name)}</span>
            <button data-action="removeChannel" data-method="${method}" data-channel="${channelId}" class="text-red-400 hover:text-red-300 text-xs">✕</button></div>
            <input type="hidden" id="${method}_${channelId}_name" value="${jsAttr(name)}">
        </div>`;
    } else if (method === 'email') {
        const smtp_server = document.getElementById('newEmailSmtp').value.trim();
        const smtp_port = document.getElementById('newEmailPort').value.trim() || 587;
        const username = document.getElementById('newEmailUser').value.trim();
        const password = document.getElementById('newEmailPass').value;
        const to_email = document.getElementById('newEmailTo').value.trim();
        if (!smtp_server || !username || !to_email) return alert('Заповніть всі поля email!');
        __secrets[channelId] = { smtp_server, smtp_port: parseInt(smtp_port), username, password, to_email };
        html = `<div class="channel-item p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 mb-2" id="ch_${channelId}">
            <div class="flex justify-between items-center"><span class="text-sm font-medium">📧 ${escHtml(name)}</span>
            <button data-action="removeChannel" data-method="${method}" data-channel="${channelId}" class="text-red-400 hover:text-red-300 text-xs">✕</button></div>
            <input type="hidden" id="${method}_${channelId}_name" value="${jsAttr(name)}">
        </div>`;
    } else {
        const webhookUrl = document.getElementById('newWebhookUrl').value.trim();
        if (!webhookUrl) return alert('Введіть URL webhook!');
        __secrets[channelId] = { webhook_url: webhookUrl };
        html = `<div class="channel-item p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 mb-2" id="ch_${channelId}">
            <div class="flex justify-between items-center"><span class="text-sm font-medium">🔗 ${escHtml(name)}</span>
            <button data-action="removeChannel" data-method="${method}" data-channel="${channelId}" class="text-red-400 hover:text-red-300 text-xs">✕</button></div>
            <input type="hidden" id="${method}_${channelId}_name" value="${jsAttr(name)}">
        </div>`;
    }
    container.insertAdjacentHTML('beforeend', html);
    closeAddChannelModal();
}
function removeChannel(method, channelId) { const el = document.getElementById('ch_' + channelId); if (el) el.remove(); delete __secrets[channelId]; }

var __secrets = {};
function getSecrets() {
    try { return JSON.parse(document.getElementById('channel-secrets')?.textContent || '{}'); } catch { return {}; }
}

async function saveNotifySettings() {
    const secrets = getSecrets();
    const settings = {};
    ['telegram','discord','teams','email','slack','sms','webhook'].forEach(m => {
        settings[m] = { enabled: document.getElementById('toggle-' + m)?.checked || false, channels: [] };
        const container = document.getElementById('channels-' + m);
        const cfg = secrets[m] || {};
        const chMap = {};
        (cfg.channels || []).forEach(ch => { chMap[ch.id] = ch; });
        if (container) {
            container.querySelectorAll('[id^="ch_"]').forEach(item => {
                const id = item.id.replace('ch_', '');
                const name = document.getElementById(m + '_' + id + '_name')?.value;
                if (!name) return;
                const existing = chMap[id] || {};
                const pending = __secrets[id] || {};
                const val = (suffix, field) => pending[field] || (document.getElementById(m + '_' + id + suffix)?.value) || existing[field] || '';
                if (m === 'telegram') {
                    const token = val('_token', 'token');
                    const chat_id = val('_chat_id', 'chat_id');
                    const message_thread_id = val('_message_thread_id', 'message_thread_id');
                    if (token && chat_id) settings[m].channels.push({id, name, token, chat_id, message_thread_id});
                } else if (m === 'email') {
                    const smtp_server = val('_smtp_server', 'smtp_server');
                    const smtp_port = parseInt(val('_smtp_port', 'smtp_port')) || existing.smtp_port || 587;
                    const username = val('_username', 'username');
                    const password = val('_password', 'password');
                    const to_email = val('_to_email', 'to_email');
                    if (smtp_server && username && to_email) settings[m].channels.push({id, name, smtp_server, smtp_port, username, password, to_email});
                } else {
                    const webhook_url = val('_webhook_url', 'webhook_url');
                    if (webhook_url) settings[m].channels.push({id, name, webhook_url});
                }
            });
        }
    });
    try {
        await fetch('/api/notify-settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(settings)});
        alert('✅ Налаштування збережено!');
    } catch(e) { console.error(e); }
}

async function loadAlertPolicy() {
    try {
        const resp = await fetch('/api/alert-policy');
        const data = await resp.json();
        document.getElementById('alertSslDays').value = (data.ssl_notification_days || [30,14,7,5,3,1]).join(', ');
        document.getElementById('alertSslCooldown').value = data.ssl_notification_cooldown_seconds ?? 21600;
        document.getElementById('alertSslInterval').value = data.ssl_check_interval_hours ?? 6;
        document.getElementById('alertTreat4xx').checked = data.treat_4xx_as_down !== false;
        document.getElementById('alertVerifySsl').checked = data.verify_ssl !== false;
    } catch(e) { console.error('loadAlertPolicy', e); }
}
async function saveAlertPolicy() {
    const getNum = (id) => { const v = parseInt(document.getElementById(id).value); return isNaN(v) ? null : v; };
    const getChecked = (id) => document.getElementById(id).checked;
    const parseCsv = (id) => document.getElementById(id).value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    const payload = {
        ssl_notification_days: parseCsv('alertSslDays'),
        ssl_notification_cooldown_seconds: getNum('alertSslCooldown'),
        ssl_check_interval_hours: getNum('alertSslInterval'),
        treat_4xx_as_down: getChecked('alertTreat4xx'),
        verify_ssl: getChecked('alertVerifySsl'),
    };
    try {
        await fetch('/api/alert-policy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        alert('✅ Політику сповіщень збережено!');
    } catch(e) { console.error(e); }
}

async function loadAppSettings() {
    try {
        const resp = await fetch('/api/app-settings');
        const data = await resp.json();
        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        setVal('displayAddress', data.display_address);
        setVal('siteTitle', data.site_title);
        setVal('logoUrl', data.logo_url);
        setVal('footerText', data.footer_text);
        const pc = document.getElementById('primaryColor');
        if (pc) pc.value = data.primary_color || '#00ff88';
        const bac = document.getElementById('brandAccentColor');
        if (bac) bac.value = data.brand_accent_color || '#06b6d4';
    } catch(e) {}
}
async function saveStatusSettings() {
    const getVal = (id) => document.getElementById(id)?.value || '';
    const payload = {
        display_address: getVal('displayAddress'),
        site_title: getVal('siteTitle'),
        logo_url: getVal('logoUrl'),
        footer_text: getVal('footerText'),
        primary_color: getVal('primaryColor') || '#00ff88',
        brand_accent_color: getVal('brandAccentColor') || '#06b6d4',
    };
    try {
        await fetch('/api/app-settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        alert('✅ Налаштування сторінки збережено!');
    } catch(e) { console.error(e); }
}

function openEditModal(id, name, url, notifyMethods, checkInterval, requestTimeout, retryInterval, maxRetries, upThreshold, monitorType, keyword, tagsEncoded) {
    document.getElementById('editSiteId').value = id;
    document.getElementById('editSiteName').value = name;
    document.getElementById('editSiteUrl').value = decodeURIComponent(url);
    document.getElementById('editSiteInterval').value = checkInterval || 60;
    document.getElementById('editSiteRequestTimeout').value = requestTimeout || 30;
    document.getElementById('editSiteRetryInterval').value = retryInterval || 20;
    document.getElementById('editSiteMaxRetries').value = maxRetries ?? 3;
    document.getElementById('editSiteUpThreshold').value = upThreshold || 2;
    document.getElementById('editSiteType').value = monitorType || 'http';
    document.getElementById('editSiteKeyword').value = keyword ? decodeURIComponent(keyword) : '';
    toggleKeywordField('editSiteType', 'editKeywordFieldContainer');

    selectedEditTags = tagsEncoded ? JSON.parse(decodeURIComponent(tagsEncoded)) : [];
    if (!Array.isArray(selectedEditTags)) selectedEditTags = [];
    renderTagsWidget('edit');
    updateExistingTagsSuggest('editExistingTagsContainer', 'editSiteTagsInput', 'edit');

    const methods = typeof notifyMethods === 'string' ? JSON.parse(decodeURIComponent(notifyMethods)) : notifyMethods || [];
    const editChannelIds = channelIdsFromMethods(methods);
    renderNotifyChannelOptions('editSiteNotify', editChannelIds);
    document.getElementById('editModal').classList.remove('hidden');
    document.getElementById('editModal').classList.add('flex');
}
function closeEditModal() { document.getElementById('editModal').classList.add('hidden'); document.getElementById('editModal').classList.remove('flex'); }
async function saveEdit() {
    const id = document.getElementById('editSiteId').value;
    const name = document.getElementById('editSiteName').value.trim();
    const url = document.getElementById('editSiteUrl').value.trim();
    const monitorType = document.getElementById('editSiteType').value;
    const keyword = document.getElementById('editSiteKeyword').value.trim();
    const checkInterval = parseInt(document.getElementById('editSiteInterval').value) || 60;
    const requestTimeout = parseInt(document.getElementById('editSiteRequestTimeout').value) || 30;
    const retryInterval = parseInt(document.getElementById('editSiteRetryInterval').value) || 20;
    const maxRetries = parseInt(document.getElementById('editSiteMaxRetries').value);
    const upThreshold = parseInt(document.getElementById('editSiteUpThreshold').value) || 2;
    
    const tags = selectedEditTags;

    const notify_methods = getSelectedNotifyMethods('editSiteNotify');
    if (!name || !url) return alert('Fill all fields!');
    try {
        await fetch('/api/sites/' + id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                url,
                monitor_type: monitorType,
                check_interval: checkInterval,
                request_timeout_seconds: requestTimeout,
                retry_interval_seconds: retryInterval,
                max_retries: Number.isNaN(maxRetries) ? 3 : maxRetries,
                up_success_threshold: upThreshold,
                notify_methods,
                keyword,
                tags
            })
        });
        closeEditModal();
        loadSites();
    } catch (e) {
        console.error(e);
    }
}

function toggleMaintRuleFields() {
    const type = document.getElementById('maintRuleType').value;
    if (type === 'one_off') {
        document.getElementById('maintOneOffFields').classList.remove('hidden');
        document.getElementById('maintRecurringFields').classList.add('hidden');
    } else {
        document.getElementById('maintOneOffFields').classList.add('hidden');
        document.getElementById('maintRecurringFields').classList.remove('hidden');
        
        const dow = document.getElementById('maintDayOfWeekContainer');
        if (type === 'weekly') {
            dow.classList.remove('hidden');
        } else {
            dow.classList.add('hidden');
        }
    }
}

async function loadMaintenanceWindows() {
    try {
        const resp = await fetch('/api/sites');
        const sites = await resp.json();
        const select = document.getElementById('maintSiteId');
        if (select) {
            select.innerHTML = '<option value="">Всі монітори</option>';
            sites.forEach(s => {
                select.innerHTML += `<option value="${s.id}">${escHtml(s.name)}</option>`;
            });
        }
    } catch(e) {
        console.error(e);
    }

    try {
        const resp = await fetch('/api/maintenance-windows');
        const windows = await resp.json();
        renderMaintenanceWindows(windows);
    } catch(e) {
        console.error(e);
    }
}

function renderMaintenanceWindows(windows) {
    const tbody = document.getElementById('maintenanceList');
    if (!tbody) return;
    if (windows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="py-10 text-center text-slate-500">Немає запланованих робіт.</td></tr>';
        return;
    }
    let html = '';
    windows.forEach(w => {
        const siteName = w.site_name || 'Всі монітори';
        let schedule = '';
        if (w.rule_type === 'one_off') {
            const start = new Date(w.start_time).toLocaleString('uk-UA');
            const end = new Date(w.end_time).toLocaleString('uk-UA');
            schedule = `<div>${escHtml(start)}</div><div class="text-xs text-slate-500">до ${escHtml(end)}</div>`;
        } else if (w.rule_type === 'daily') {
            schedule = `<div>Щодня о ${escHtml(w.start_hour_minute)}</div><div class="text-xs text-slate-500">Тривалість: ${escHtml(w.duration_minutes)} хв</div>`;
        } else if (w.rule_type === 'weekly') {
            const days = ['', 'Пн', 'Вв', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'];
            const dayName = days[w.day_of_week] || '';
            schedule = `<div>Щотижня (${escHtml(dayName)}) о ${escHtml(w.start_hour_minute)}</div><div class="text-xs text-slate-500">Тривалість: ${escHtml(w.duration_minutes)} хв</div>`;
        }

        const checked = w.is_active ? 'checked' : '';
        const toggleBtn = `<label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" ${checked} class="sr-only peer" data-change="toggleMaintWindow" data-id="${w.id}">
            <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:height-4 after:w-4 after:h-4 after:transition-all peer-checked:bg-accent"></div>
        </label>`;

        html += `<tr class="border-b border-slate-800/30 hover:bg-slate-800/10">
            <td class="py-3.5 px-4">
                <div class="font-medium">${escHtml(w.name)}</div>
                <div class="text-xs text-slate-400">${escHtml(siteName)}</div>
            </td>
            <td class="py-3.5 px-4">${schedule}</td>
            <td class="py-3.5 px-4 text-center">${toggleBtn}</td>
            <td class="py-3.5 px-4 text-right">
                <button data-action="deleteMaintWindow" data-id="${w.id}" class="text-red-400 hover:text-red-300 transition">🗑️ Видалити</button>
            </td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

async function addMaintenanceWindow() {
    const name = document.getElementById('maintName').value.trim();
    const siteIdVal = document.getElementById('maintSiteId').value;
    const ruleType = document.getElementById('maintRuleType').value;
    
    if (!name) return alert('Введіть назву періоду!');
    
    const payload = {
        name,
        site_id: siteIdVal ? parseInt(siteIdVal) : null,
        rule_type: ruleType
    };
    
    if (ruleType === 'one_off') {
        const start = document.getElementById('maintStartTime').value;
        const end = document.getElementById('maintEndTime').value;
        if (!start || !end) return alert('Виберіть час початку та кінця!');
        payload.start_time = new Date(start).toISOString();
        payload.end_time = new Date(end).toISOString();
    } else {
        const startHM = document.getElementById('maintStartHourMinute').value.trim();
        const duration = parseInt(document.getElementById('maintDurationMinutes').value);
        if (!startHM || !duration) return alert('Введіть час початку та тривалість!');
        
        if (!/^\d{2}:\d{2}$/.test(startHM)) return alert('Введіть час у форматі ГГ:ХХ (напр. 03:00)!');
        
        payload.start_hour_minute = startHM;
        payload.duration_minutes = duration;
        
        if (ruleType === 'weekly') {
            payload.day_of_week = parseInt(document.getElementById('maintDayOfWeek').value);
        }
    }
    
    try {
        const resp = await fetch('/api/maintenance-windows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (resp.ok) {
            document.getElementById('maintName').value = '';
            document.getElementById('maintStartTime').value = '';
            document.getElementById('maintEndTime').value = '';
            document.getElementById('maintStartHourMinute').value = '';
            document.getElementById('maintDurationMinutes').value = '';
            loadMaintenanceWindows();
            alert('Період обслуговування додано!');
        } else {
            const err = await resp.json();
            alert('Помилка: ' + (err.detail || 'невідома помилка'));
        }
    } catch(e) {
        console.error(e);
    }
}

async function toggleMaintWindow(id, active) {
    try {
        await fetch(`/api/maintenance-windows/${id}/toggle`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: active })
        });
    } catch(e) {
        console.error(e);
    }
}

async function deleteMaintWindow(id) {
    if (!confirm('Видалити цей період обслуговування?')) return;
    try {
        const resp = await fetch(`/api/maintenance-windows/${id}`, {
            method: 'DELETE'
        });
        if (resp.ok) {
            loadMaintenanceWindows();
        }
    } catch(e) {
        console.error(e);
    }
}

// WebSocket for real-time updates
let ws = null;
let wsReconnectTimer = null;
let wsRetries = 0;
const WS_MAX_BACKOFF = 30000; // max 30s between retries

function updateWorkerDot(connected) {
    const dot = document.getElementById('workerDot');
    const label = document.getElementById('workerLabel');
    if (!dot || !label) return;
    dot.className = `w-2 h-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-400'}`;
    label.textContent = connected ? 'Online' : 'Offline';
}

function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;
    try {
        ws = new WebSocket(url);
        ws.onopen = function() { updateWorkerDot(true); wsRetries = 0; };
        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'site_status') {
                    updateSiteCard(data);
                }
            } catch(e) { console.error('WS parse error', e); }
        };
        ws.onclose = function() {
            updateWorkerDot(false);
            ws = null;
            var delay = Math.min(1000 * Math.pow(2, wsRetries), WS_MAX_BACKOFF);
            wsRetries++;
            if (!wsReconnectTimer) {
                wsReconnectTimer = setTimeout(function() {
                    wsReconnectTimer = null;
                    connectWebSocket();
                }, delay);
            }
        };
        ws.onerror = function() {
            updateWorkerDot(false);
        };
    } catch(e) { console.error('WS connection error', e); updateWorkerDot(false); }
}

function updateSiteCard(data) {
    document.querySelectorAll(`[data-site-id="${data.site_id}"]`).forEach(card => {
        var isUp = data.status === 'up';
        var borderClass = isUp ? 'border-emerald-500' : 'border-red-500';
        card.className = card.className.replace(/border-\w+-\d+/g, '').trim() + ' ' + borderClass;
        var statusEl = card.querySelector('.status-badge');
        if (statusEl) {
            statusEl.textContent = isUp ? 'UP' : 'DOWN';
            statusEl.className = 'status-badge ' + (isUp ? 'up' : 'down');
        }
        var rtEl = card.querySelector('.response-time');
        if (rtEl && data.response_time) {
            rtEl.textContent = data.response_time + 'ms';
        }
        var codeEl = card.querySelector('.grid-cols-4 > div:last-child .text-sm.font-bold');
        if (codeEl && data.status_code) {
            codeEl.textContent = data.status_code;
        }
    });
    if (data.status !== 'up') {
        loadIncidents();
    }
}

connectWebSocket();

// Auto-refresh incidents and sites every 30s
setInterval(() => { loadIncidents(); loadSites(); }, 30000);

// Init
function saveDisplayAddress() { return saveStatusSettings(); }
initNotifyUI();
loadAppSettings();
loadSSLCertificates();
loadIncidents();
loadResponseTimeChart();
loadSSLTimelineChart();
toggleKeywordField('monitorType', 'keywordFieldContainer');
// Manual load once (HTMX handles auto-refresh)
setupTagsEventListeners();
renderTagsWidget('add');
renderTagsWidget('edit');
renderNotifyChannelOptions('siteNotifyOptions', []);
loadSites();


// --- delegated action handlers for the dashboard page ---
window.AppActions = Object.assign(window.AppActions || {}, {
  switchTab: (el) => switchTab(el.dataset.tab),
  loadDashboard: () => loadDashboard(),
  checkAllMonitors: () => checkAllMonitors(),
  checkSSLCertificates: () => checkSSLCertificates(),
  addSite: () => addSite(),
  closeEditModal: () => closeEditModal(),
  closeAddChannelModal: () => closeAddChannelModal(),
  addNewChannel: () => addNewChannel(),
  addMaintenanceWindow: () => addMaintenanceWindow(),
  saveEdit: () => saveEdit(),
  saveAlertPolicy: () => saveAlertPolicy(),
  saveNotifySettings: () => saveNotifySettings(),
  saveStatusSettings: () => saveStatusSettings(),
  setFilter: (el) => setFilter(el.dataset.filter || 'all'),
  setTagFilter: (el) => setTagFilter(el.dataset.tag || 'all'),
  checkSite: (el) => checkSite(el.dataset.id),
  deleteSite: (el) => deleteSite(el.dataset.id),
  deleteMaintWindow: (el) => deleteMaintWindow(el.dataset.id),
  openEditModal: (el) => openEditModal(
    el.dataset.id,
    el.dataset.name || '',
    el.dataset.url || '',
    el.dataset.methods || '',
    parseInt(el.dataset.interval) || 60,
    parseInt(el.dataset.timeout) || 30,
    parseInt(el.dataset.retryInterval) || 20,
    el.dataset.maxRetries === undefined ? 3 : parseInt(el.dataset.maxRetries),
    parseInt(el.dataset.upThreshold) || 2,
    el.dataset.mtype || 'http',
    el.dataset.keyword || '',
    el.dataset.tags || '[]'
  ),
  removeChannel: (el) => removeChannel(el.dataset.method, el.dataset.channel),
  removeTagChip: (el) => removeTagChip(el.dataset.type, el.dataset.tag),
  openAddChannelModal: (el) => openAddChannelModal(el.dataset.method),
  focusInput: (el) => { const inp = document.getElementById(el.dataset.target); if (inp) inp.focus(); },
});

window.AppChange = Object.assign(window.AppChange || {}, {
  renderMonitors: () => renderMonitors(),
  toggleKeywordFieldAdd: () => toggleKeywordField('monitorType', 'keywordFieldContainer'),
  toggleKeywordFieldEdit: () => toggleKeywordField('editSiteType', 'editKeywordFieldContainer'),
  toggleMaintRuleFields: () => toggleMaintRuleFields(),
  toggleMaintWindow: (el) => toggleMaintWindow(el.dataset.id, el.checked),
  updateChannelFields: () => updateChannelFields(),
  toggleNotify: (el) => toggleNotify(el.dataset.method),
});

window.AppKeyup = Object.assign(window.AppKeyup || {}, {
  renderMonitors: () => renderMonitors(),
});
