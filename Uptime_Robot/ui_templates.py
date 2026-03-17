"""
Module for UI Templates (HTML, CSS, JS)
# Refactoring in progress
"""

# Public Status Page Template
PUBLIC_STATUS_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status - Uptime Monitor</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: #0f0f23; color: #fff; min-height: 100vh; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #0f0f23); padding: 40px; text-align: center; border-bottom: 1px solid #2a2a4a; }}
        .logo {{ font-size: 32px; font-weight: 700; margin-bottom: 20px; }}
        .logo-icon {{ display: inline-block; width: 50px; height: 50px; background: linear-gradient(135deg, #00d9ff, #00ff88); border-radius: 12px; line-height: 50px; font-size: 24px; margin-right: 10px; }}
        .overall-status {{ font-size: 48px; font-weight: 700; margin: 30px 0; }}
        .overall-status.up {{ color: #00ff88; }}
        .overall-status.down {{ color: #ff4757; }}
        .stats {{ display: flex; justify-content: center; gap: 40px; margin: 20px 0; }}
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 36px; font-weight: 700; }}
        .stat-label {{ color: #a0a0b0; font-size: 14px; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 40px; }}
        .monitor {{ background: linear-gradient(145deg, #1a1a2e, #16213e); padding: 20px; margin-bottom: 15px; border-radius: 15px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #2a2a4a; }}
        .monitor.up {{ border-left: 4px solid #00ff88; }}
        .monitor.down {{ border-left: 4px solid #ff4757; }}
        .monitor.unknown {{ border-left: 4px solid #94a3b8; }}
        .monitor-name {{ font-size: 18px; font-weight: 600; }}
        .monitor-url {{ color: #a0a0b0; font-size: 13px; margin-top: 5px; }}
        .status-badge {{ padding: 8px 20px; border-radius: 20px; font-weight: 600; font-size: 14px; }}
        .status-badge.up {{ background: rgba(0,255,136,0.15); color: #00ff88; }}
        .status-badge.down {{ background: rgba(255,71,87,0.15); color: #ff4757; }}
        .status-badge.unknown {{ background: rgba(148,163,184,0.15); color: #94a3b8; }}
        .footer {{ text-align: center; padding: 40px; color: #a0a0b0; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo"><span class="logo-icon">⚡</span>Uptime Monitor</div>
        <div class="overall-status {overall_status_class}">
            {overall_status_text}
        </div>
        <div class="stats">
            <div class="stat"><div class="stat-value" style="color: #00d9ff;">{total}</div><div class="stat-label">Моніторів</div></div>
            <div class="stat"><div class="stat-value" style="color: #00ff88;">{up_count}</div><div class="stat-label">Онлайн</div></div>
            <div class="stat"><div class="stat-value" style="color: #ff4757;">{down_count}</div><div class="stat-label">Офлайн</div></div>
        </div>
    </div>
    <div class="container">{monitors_html}
    </div>
    <div class="footer"><p>Оновлено: {timestamp}</p></div>
</body>
</html>"""

# Dashboard HTML Template
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Dashboard</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⏱️</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16162a;
            --bg-card: #0f0f1a;
            --accent: #00d9ff;
            --accent-hover: #00a8cc;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --border: #334155;
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg-gradient); color: var(--text-primary); min-height: 100vh; }}

        .header {{ background: rgba(15, 23, 42, 0.95); padding: 16px 32px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; backdrop-filter: blur(20px); position: sticky; top: 0; z-index: 100; }}
        .logo {{ font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 12px; }}
        .logo-icon {{ width: 40px; height: 40px; background: linear-gradient(135deg, var(--accent), #06b6d4); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3); }}

        .hero-stats {{ display: flex; gap: 24px; margin: 32px; background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)); padding: 28px 36px; border-radius: 20px; border: 1px solid rgba(148, 163, 184, 0.1); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}
        .hero-stat {{ text-align: center; flex: 1; position: relative; padding: 0 20px; }}
        .hero-stat:not(:last-child)::after {{ content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); height: 50%; width: 1px; background: var(--border); }}
        .hero-stat-value {{ font-size: 42px; font-weight: 700; color: var(--accent); text-shadow: 0 0 30px rgba(0, 217, 255, 0.3); }}
        .hero-stat-label {{ color: var(--text-secondary); font-size: 13px; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }}

        .monitoring-types {{ display: flex; gap: 12px; margin: 0 32px 24px; flex-wrap: wrap; }}
        .monitor-type-btn {{ padding: 10px 20px; background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border); border-radius: 10px; cursor: pointer; font-weight: 500; color: var(--text-secondary); transition: all 0.3s ease; display: flex; align-items: center; gap: 8px; font-size: 13px; }}
        .monitor-type-btn:hover {{ border-color: var(--accent); color: var(--text-primary); background: rgba(0, 217, 255, 0.1); }}
        .monitor-type-btn.active {{ background: linear-gradient(135deg, var(--accent), #06b6d4); color: #000; border-color: var(--accent); font-weight: 600; }}

        .container {{ max-width: 1400px; margin: 0 auto; padding: 0 32px 32px; }}
        #tab-dashboard .container {{
            max-width: none !important;
            margin: 0 !important;
            width: 100% !important;
            padding: 0 12px 32px !important;
        }}

        .panel {{ background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%); padding: 24px; border-radius: 16px; margin-bottom: 24px; border: 1px solid rgba(148, 163, 184, 0.1); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); transition: all 0.3s ease; }}
        .panel:hover {{ border-color: rgba(0, 217, 255, 0.3); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4); }}
        .panel-title {{ font-size: 16px; font-weight: 600; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; color: var(--text-primary); }}

        .chart-container {{ position: relative; height: 280px; margin: 16px 0; }}

        .monitor-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }}
        .monitor-card {{ background: linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%); padding: 20px; border-radius: 16px; border: 1px solid rgba(148, 163, 184, 0.1); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); position: relative; overflow: hidden; }}
        .monitor-card:hover {{ transform: translateY(-5px) scale(1.02); box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 30px rgba(0,217,255,0.1); }}
        .monitor-card.up {{ border-left: 4px solid var(--success); }}
        .monitor-card.down {{ border-left: 4px solid var(--danger); }}
        .monitor-card.paused {{ border-left: 4px solid var(--warning); opacity: 0.7; }}

        .monitor-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }}
        .monitor-name {{ font-size: 18px; font-weight: 600; }}
        .monitor-url {{ color: var(--text-secondary); font-size: 13px; word-break: break-all; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px; }}
        .monitor-type-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; background: rgba(0,255,136,0.15); color: var(--accent); }}

        .monitor-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; padding: 12px 0; border-top: 1px solid rgba(148, 163, 184, 0.1); border-bottom: 1px solid rgba(148, 163, 184, 0.1); }}
        .monitor-stat {{ text-align: center; }}
        .monitor-stat-value {{ font-size: 16px; font-weight: 600; }}
        .monitor-stat-label {{ font-size: 11px; color: var(--text-secondary); margin-top: 4px; }}

        .monitor-actions {{ display: flex; gap: 8px; margin-top: 16px; }}
        .btn {{ flex: 1; padding: 10px; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; font-size: 12px; transition: all 0.2s ease; position: relative; z-index: 10; }}
        .btn-check {{ background: linear-gradient(135deg, var(--accent), #06b6d4); color: #000; }}
        .btn-edit {{ background: rgba(245, 158, 11, 0.15); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.3); }}
        .btn-delete {{ background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }}

        .modal {{ display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.7); z-index: 1000; align-items: center; justify-content: center; backdrop-filter: blur(4px); }}
        .modal.active {{ display: flex; }}
        .modal-content {{ background: linear-gradient(180deg, #1e293b, #0f172a); padding: 28px; border-radius: 16px; max-width: 480px; width: 90%; border: 1px solid var(--border); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}

        .tabs {{ display: flex; gap: 8px; margin: 0 32px; padding: 4px; background: rgba(15, 23, 42, 0.6); border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.1); width: fit-content; }}
        .tab-btn {{ padding: 10px 24px; background: transparent; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; color: var(--text-secondary); transition: all 0.2s ease; font-size: 14px; }}
        .tab-btn.active {{ background: linear-gradient(135deg, var(--accent), #06b6d4); color: #000; font-weight: 600; }}

        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; animation: fadeSlideIn 0.4s ease; }}

        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        @keyframes fadeSlideIn {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}

        .notify-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
        .notify-card {{ background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%); padding: 20px; border-radius: 14px; border: 1px solid rgba(148, 163, 184, 0.1); transition: all 0.2s ease; }}
        .notify-card:hover {{ border-color: rgba(0, 217, 255, 0.3); box-shadow: 0 0 20px rgba(0, 217, 255, 0.1); }}
        .notify-card.enabled {{ border-color: rgba(34, 197, 94, 0.4); background: linear-gradient(180deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%); }}
        .notify-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}

        .edit-notify-options {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
        .notify-option {{ display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: 10px; background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); cursor: pointer; transition: all 0.2s; }}
        .notify-option:hover {{ border-color: var(--accent); background: rgba(0, 217, 255, 0.1); }}
        .notify-option input[type="checkbox"] {{ width: 18px; height: 18px; accent-color: var(--accent); cursor: pointer; }}
        .notify-option span {{ font-size: 13px; color: var(--text-primary); }}

        .add-channel-btn {{ display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px; border-radius: 14px; background: rgba(15, 23, 42, 0.4); border: 2px dashed var(--border); color: var(--text-secondary); cursor: pointer; transition: all 0.2s; }}
        .add-channel-btn:hover {{ border-color: var(--accent); color: var(--accent); background: rgba(0, 217, 255, 0.05); }}

        .toggle {{ position: relative; display: inline-block; width: 44px; height: 24px; }}
        .toggle input {{ opacity: 0; width: 0; height: 0; }}
        .toggle-slider {{ position: absolute; cursor: pointer; inset: 0; background: rgba(30, 41, 59, 0.8); border-radius: 24px; transition: 0.2s; border: 1px solid var(--border); }}
        .toggle-slider::before {{ content: ''; position: absolute; height: 18px; width: 18px; left: 2px; bottom: 2px; background: var(--text-secondary); border-radius: 50%; transition: 0.2s; }}
        .toggle input:checked + .toggle-slider {{ background: var(--accent); border-color: var(--accent); }}
        .toggle input:checked + .toggle-slider::before {{ transform: translateX(20px); background: #000; }}

        .notify-fields {{ display: flex; flex-direction: column; gap: 10px; }}
        .notify-fields input {{ width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 13px; }}
        .notify-fields input:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.1); }}

        .btn-add-channel {{ padding: 10px 18px; background: linear-gradient(135deg, var(--accent), #06b6d4); border: none; border-radius: 8px; color: #000; font-weight: 600; cursor: pointer; font-size: 13px; transition: all 0.2s; }}
        .btn-add-channel:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3); }}

        .add-channel-card {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 30px; border-radius: 14px; background: rgba(15, 23, 42, 0.3); border: 2px dashed var(--border); cursor: pointer; transition: all 0.2s; min-height: 140px; }}
        .add-channel-card:hover {{ border-color: var(--accent); background: rgba(0, 217, 255, 0.05); }}

        .channels-list {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }}
        .channel-item {{ background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }}
        .channel-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .channel-name {{ font-weight: 500; color: var(--text-primary); }}
        .btn-remove-channel {{ background: rgba(239, 68, 68, 0.2); border: none; color: #ef4444; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        .btn-remove-channel:hover {{ background: rgba(239, 68, 68, 0.4); }}
        .btn-add-channel-inline {{ width: 100%; padding: 12px; background: rgba(0, 217, 255, 0.1); border: 1px dashed var(--accent); border-radius: 10px; color: var(--accent); cursor: pointer; font-size: 13px; transition: all 0.2s; }}
        .btn-add-channel-inline:hover {{ background: rgba(0, 217, 255, 0.2); }}

        .btn-save-notify {{ margin-top: 24px; width: 100%; padding: 16px; background: linear-gradient(135deg, var(--accent), #00d9ff); border: none; border-radius: 12px; color: #000; font-weight: 600; font-size: 15px; cursor: pointer; transition: all 0.2s; }}
        .btn-save-notify:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 217, 255, 0.3); }}

        .form-row {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
        .form-row input, .form-row select {{ flex: 1; min-width: 180px; padding: 12px; border-radius: 10px; background: rgba(15, 23, 42, 0.8); color: var(--text-primary); border: 1px solid var(--border); font-size: 14px; }}

        .ssl-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}

        .header-btn {{ padding: 8px 16px; background: rgba(0, 217, 255, 0.15); color: var(--accent); text-decoration: none; border-radius: 8px; font-size: 13px; font-weight: 500; transition: all 0.2s; border: 1px solid transparent; }}
        .header-btn.danger {{ background: rgba(239, 68, 68, 0.15); color: var(--danger); }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo"><div class="logo-icon">⚡</div><span>Uptime Monitor</span></div>
        <div style="display: flex; align-items: center; gap: 16px;">
            <div id="lastUpdate" style="color: var(--text-secondary); font-size: 13px;"></div>
            <a href="/status" target="_blank" class="header-btn">📄 Status</a>
            <a href="/users" class="header-btn">👥 Користувачі</a>
            <a href="/logout" class="header-btn danger">🚪 Вийти</a>
        </div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('dashboard')">Dashboard</button>
        <button class="tab-btn" onclick="switchTab('ssl')">SSL</button>
        <button class="tab-btn" onclick="switchTab('incidents')">Incidents</button>
        <button class="tab-btn" onclick="switchTab('settings')">Settings</button>
    </div>

    <div id="tab-dashboard" class="tab-content active">
        <div class="hero-stats">
            <div class="hero-stat">
                <div class="hero-stat-value">{total_sites}</div>
                <div class="hero-stat-label">Моніторів</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-value" style="color: var(--success);">{up_sites}</div>
                <div class="hero-stat-label">Онлайн</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-value" style="color: var(--danger);">{down_sites}</div>
                <div class="hero-stat-label">Офлайн</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-value" style="color: var(--warning);">0</div>
                <div class="hero-stat-label">Інцидентів</div>
            </div>
        </div>

        <div class="container">
            <div class="panel">
                <div class="panel-title">📊 Monitors Timeline (24h)</div>
                <div style="display: flex; align-items: flex-end; gap: 10px; margin-bottom: 10px; padding: 0 10px;">
                    <div style="display: flex; gap: 4px; align-items: center; font-size: 10px;">
                        <div style="width: 12px; height: 12px; background: #22c55e; border-radius: 2px;"></div>
                        <span style="color: var(--text-secondary);">UP</span>
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center; font-size: 10px;">
                        <div style="width: 12px; height: 12px; background: #ef4444; border-radius: 2px;"></div>
                        <span style="color: var(--text-secondary);">DOWN</span>
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center; font-size: 10px;">
                        <div style="width: 12px; height: 12px; background: #eab308; border-radius: 2px;"></div>
                        <span style="color: var(--text-secondary);">SLOW</span>
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center; font-size: 10px;">
                        <div style="width: 12px; height: 12px; background: #6b7280; border-radius: 2px;"></div>
                        <span style="color: var(--text-secondary);">NO DATA</span>
                    </div>
                </div>
                <div id="uptimeChartContainer" style="padding: 10px; max-height: 500px; overflow-y: auto;"></div>
            </div>

            <div class="panel">
                <div class="panel-title">🎯 Швидкі дії</div>
                <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                    <button class="btn btn-check" style="background: linear-gradient(135deg, #00ff88, #00cc6a);" onclick="checkAllMonitors()">🔄 Перевірити всі</button>
                    <button class="btn btn-check" onclick="loadDashboard()">📊 Оновити дані</button>
                    <button class="btn btn-edit" onclick="switchTab('incidents')">⚠️ Інциденти</button>
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">📊 Статус всіх моніторів</div>
                <div class="monitor-grid" id="dashboardMonitors"></div>
            </div>
        </div>
    </div>

    <div id="tab-incidents" class="tab-content">
        <div class="container">
            <div class="panel">
                <div class="panel-title">⚠️ Історія інцидентів</div>
                <div id="incidentsList" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    Немає інцидентів - всі монітори працюють!
                </div>
            </div>
        </div>
    </div>

    <div id="tab-settings" class="tab-content">
        <div class="container">
            <div class="panel">
                <div class="panel-title">➕ Додати новий монітор</div>
                <div class="form-row">
                    <input type="text" id="siteName" placeholder="Назва">
                    <input type="url" id="siteUrl" placeholder="URL">
                </div>
                <div class="form-row" style="margin-top: 15px;">
                    <select id="monitorType">
                        <option value="http">🌐 HTTP(S)</option>
                        <option value="port">🔌 Порт</option>
                        <option value="ping">📡 Пінг</option>
                        <option value="ssl">🔒 SSL</option>
                    </select>
                </div>
                <div class="modal-field" style="margin-top: 16px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 10px; display: block;">Способи сповіщень</label>
                    <div class="edit-notify-options" id="siteNotifyOptions">
                        <label class="notify-option"><input type="checkbox" value="telegram"><span>📱 Telegram</span></label>
                        <label class="notify-option"><input type="checkbox" value="discord"><span>🎮 Discord</span></label>
                        <label class="notify-option"><input type="checkbox" value="teams"><span>🏢 MS Teams</span></label>
                        <label class="notify-option"><input type="checkbox" value="email"><span>📧 Email</span></label>
                    </div>
                </div>
                <button class="btn btn-check" style="margin-top: 20px; width: 100%;" onclick="addSite()">➕ Додати монітор</button>
            </div>

            <div class="panel">
                <div class="panel-title">🔗 Налаштування адреси</div>
                <div class="address-config">
                    <div class="form-row">
                        <input type="text" id="displayAddress" placeholder="Адреса доступу">
                        <button onclick="saveDisplayAddress()">💾 Зберегти</button>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">🔔 Глобальні налаштування сповіщень</div>
                <div class="notify-grid" id="notifyGrid">
                    <!-- Notification Cards here -->
                    {notification_cards}
                </div>
                <div class="add-channel-card" onclick="openAddChannelModal()">
                    <span style="font-size: 28px;">➕</span>
                    <span style="font-size: 14px; color: var(--text-secondary);">Додати новий канал сповіщень</span>
                </div>
                <button class="btn-save-notify" onclick="saveNotifySettings()">💾 Зберегти налаштування</button>
            </div>
        </div>
    </div>

    <div id="tab-ssl" class="tab-content">
        <div class="panel">
            <div class="panel-title" style="display:flex; justify-content:space-between;">
                <span>🔒 SSL Сертифікати</span>
                <button class="btn btn-check" onclick="checkSSLCertificates()" style="padding:8px 20px;">🔄 Перевірити зараз</button>
            </div>
            <div class="ssl-grid" id="sslGrid"></div>
        </div>
    </div>

    <div class="modal" id="editModal">
        <div class="modal-content" style="max-width: 520px;">
            <div class="modal-title" style="margin-bottom: 24px; font-size: 22px;">✏️ Редагування сайту</div>
            <input type="hidden" id="editSiteId">
            <div class="modal-field">
                <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; display: block;">Назва</label>
                <input type="text" id="editSiteName" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 15px;">
            </div>
            <div class="modal-field" style="margin-top: 16px;">
                <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; display: block;">URL</label>
                <input type="url" id="editSiteUrl" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 15px;">
            </div>
            <div class="modal-field" style="margin-top: 16px;">
                <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 10px; display: block;">Способи сповіщень</label>
                <div class="edit-notify-options" id="editSiteNotify">
                    <label class="notify-option"><input type="checkbox" value="telegram"><span>📱 Telegram</span></label>
                    <label class="notify-option"><input type="checkbox" value="discord"><span>🎮 Discord</span></label>
                    <label class="notify-option"><input type="checkbox" value="teams"><span>🏢 MS Teams</span></label>
                    <label class="notify-option"><input type="checkbox" value="email"><span>📧 Email</span></label>
                </div>
            </div>
            <div class="modal-actions" style="margin-top: 28px; display: flex; gap: 12px;">
                <button onclick="closeEditModal()" style="flex: 1; padding: 14px; border: none; border-radius: 10px; background: rgba(148, 163, 184, 0.15); color: var(--text-primary); cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s;">Скасувати</button>
                <button onclick="saveEdit()" style="flex: 1; padding: 14px; border: none; border-radius: 10px; background: linear-gradient(135deg, var(--accent), #00d9ff); color: #000; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">💾 Зберегти</button>
            </div>
        </div>
    </div>

    <div class="modal" id="addChannelModal">
        <div class="modal-content" style="max-width: 480px;">
            <div class="modal-title" style="margin-bottom: 20px; font-size: 20px;">➕ Додати канал сповіщень</div>
            <div class="modal-field">
                <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Тип каналу</label>
                <select id="addChannelMethod" onchange="updateChannelFields()" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                    <option value="telegram">📱 Telegram</option>
                    <option value="discord">🎮 Discord</option>
                    <option value="teams">🏢 MS Teams</option>
                    <option value="email">📧 Email</option>
                </select>
            </div>
            <div class="modal-field" style="margin-top: 16px;">
                <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Назва каналу</label>
                <input type="text" id="newChannelName" placeholder="Наприклад: Основний Telegram" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
            </div>
            <div id="telegramFields" style="margin-top: 16px;">
                <div class="modal-field">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Telegram Bot Token</label>
                    <input type="text" id="newTelegramToken" placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
                <div class="modal-field" style="margin-top: 12px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Chat ID</label>
                    <input type="text" id="newTelegramChatId" placeholder="123456789" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
            </div>
            <div id="webhookFields" style="display: none; margin-top: 16px;">
                <div class="modal-field">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Webhook URL</label>
                    <input type="url" id="newWebhookUrl" placeholder="https://discord.com/api/webhooks/..." style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
            </div>
            <div id="emailFields" style="display: none; margin-top: 16px;">
                <div class="modal-field">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">SMTP Сервер</label>
                    <input type="text" id="newEmailSmtp" placeholder="smtp.gmail.com" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
                <div class="modal-field" style="margin-top: 12px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Порт</label>
                    <input type="text" id="newEmailPort" placeholder="587" value="587" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
                <div class="modal-field" style="margin-top: 12px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Username</label>
                    <input type="text" id="newEmailUser" placeholder="your@email.com" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
                <div class="modal-field" style="margin-top: 12px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Password</label>
                    <input type="password" id="newEmailPass" placeholder="Пароль" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
                <div class="modal-field" style="margin-top: 12px;">
                    <label style="color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; display: block;">Отримувач</label>
                    <input type="text" id="newEmailTo" placeholder="to@email.com" style="width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.8); color: var(--text-primary); font-size: 14px;">
                </div>
            </div>
            <div class="modal-actions" style="margin-top: 24px; display: flex; gap: 12px;">
                <button onclick="closeAddChannelModal()" style="flex: 1; padding: 14px; border: none; border-radius: 10px; background: rgba(148, 163, 184, 0.15); color: var(--text-primary); cursor: pointer; font-size: 14px; font-weight: 500;">Скасувати</button>
                <button onclick="addNewChannel()" style="flex: 1; padding: 14px; border: none; border-radius: 10px; background: linear-gradient(135deg, var(--accent), #00d9ff); color: #000; cursor: pointer; font-size: 14px; font-weight: 600;">Додати</button>
            </div>
        </div>
    </div>

    <script>
        var notifyConfig = {notify_config_json};

        {js_functions}

        initNotifyUI();
        loadAppSettings();
        loadSites();
        loadSSLCertificates();
        loadUptimeChart();
        loadIncidents();
        setInterval(loadSites, 60000);
        startIncidentsAutoRefresh();
    </script>
</body>
</html>"""

# Auth Templates
LOGIN_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Login</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .login-container {{
            background: #16213e;
            padding: 40px;
            border-radius: 15px;
            border: 1px solid #2a2a4a;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo-icon {{
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            border-radius: 15px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            margin-bottom: 15px;
        }}
        h1 {{ color: #fff; font-size: 24px; text-align: center; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #a0a0b0; font-weight: 500; }}
        input {{
            width: 100%;
            padding: 12px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            border-radius: 8px;
            font-size: 14px;
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            color: #000;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        .error {{ background: rgba(255, 71, 87, 0.15); color: #ff4757; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; border: 1px solid rgba(255, 71, 87, 0.3); }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <h1>Uptime Monitor</h1>
        </div>
        {error_message}
        <form method="POST" action="/login">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>"""

CHANGE_PASSWORD_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Change Password</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: #16213e;
            padding: 40px;
            border-radius: 15px;
            border: 1px solid #2a2a4a;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }}
        .warning-box {{
            background: rgba(255, 71, 87, 0.15);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff4757;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 25px;
            text-align: center;
        }}
        input {{
            width: 100%;
            padding: 12px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            color: #000;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Change Password</h1>
        <div class="warning-box">Please change your default password for security.</div>
        {error_message}
        <form method="POST" action="/change-password">
            <input type="password" name="current_password" placeholder="Current Password" required>
            <input type="password" name="new_password" placeholder="New Password" required minlength="6">
            <input type="password" name="confirm_password" placeholder="Confirm New Password" required>
            <button type="submit">Change Password</button>
        </form>
    </div>
</body>
</html>"""

DASHBOARD_JS = """
        let currentFilter = 'all';
        let sitesData = [];
        let sslCertificatesData = [];
        let responseChart = null;

        async function loadSites() {
            try {
                const response = await fetch('/api/sites');
                sitesData = await response.json();
                renderMonitors();
                updateStats();
                loadUptimeChart();
            } catch(e) { console.error(e); }
        }

        function updateStats() {
            const up = sitesData.filter(s => s.status === 'up').length;
            const down = sitesData.filter(s => s.status === 'down').length;
            const total = sitesData.length;

            // Update hero stats if they exist
            const vTotal = document.querySelector('.hero-stat-value:nth-child(1)');
            const vUp = document.querySelector('.hero-stat-value:nth-child(2)');
            const vDown = document.querySelector('.hero-stat-value:nth-child(3)');

            document.getElementById('lastUpdate').innerText = 'Останнє оновлення: ' + new Date().toLocaleTimeString();
        }

        async function loadUptimeChart() {
            const container = document.getElementById('uptimeChartContainer');
            if (!container) return;

            try {
                // Get server time first for synchronization
                const timeResponse = await fetch('/api/server-time');
                const serverTime = await timeResponse.json();
                const serverNow = new Date(serverTime.timestamp * 1000);

                const response = await fetch('/api/sites');
                let sites = await response.json();

                if (sites.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 40px;">Немає моніторів</div>';
                    return;
                }

                // Sort: DOWN first (priority), then slow/unknown, then UP
                sites.sort((a, b) => {
                    const statusOrder = { 'down': 0, 'slow': 1, 'paused': 2, 'unknown': 3, 'up': 4 };
                    const orderA = statusOrder[a.status] ?? 5;
                    const orderB = statusOrder[b.status] ?? 5;
                    return orderA - orderB;
                });

                // 24h window aligned to "last 24 hours" from SERVER time
                const now = serverNow;
                const nowMs = now.getTime();
                const windowStartMs = nowMs - (24 * 60 * 60 * 1000);
                const chartWidth = Math.max(600, container.clientWidth - 200);
                const chartHeight = 40;

                // Generate hour markers with REAL time labels (server time)
                const hourMarkers = [];
                const timeLabels = [];
                for (let h = 0; h <= 24; h += 4) {
                    const x = (h / 24) * chartWidth;
                    // Calculate actual time for this position (server time)
                    const markerTime = new Date(windowStartMs + (h * 60 * 60 * 1000));
                    const timeLabel = markerTime.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
                    hourMarkers.push(`<div style="position: absolute; left: ${x}px; top: 0; bottom: 0; width: 1px; background: rgba(100,100,100,0.3); z-index: 1;"></div>`);
                    timeLabels.push(`<div style="position: absolute; left: ${x}px; top: 0; font-size: 10px; color: var(--text-secondary); transform: translateX(-50%); white-space: nowrap;">${timeLabel}</div>`);
                }

                // Current time marker - precise position with hours, minutes, seconds (SERVER time)
                const currentHour = now.getHours();
                const currentMinute = now.getMinutes();
                const currentSecond = now.getSeconds();
                const preciseCurrentHour = currentHour + (currentMinute / 60) + (currentSecond / 3600);
                const nowX = (preciseCurrentHour / 24) * chartWidth;

                let siteCharts = '';

                for (const site of sites) {
                    const historyRes = await fetch(`/api/sites/${site.id}/history?limit=200`);
                    const history = await historyRes.json();

                    // Group by hour
                    const hourlyData = {};
                    for (let h = 0; h < 24; h++) {
                        hourlyData[h] = {up: 0, down: 0, slow: 0, total: 0};
                    }

                    history.forEach(h => {
                        const ts = new Date(h.checked_at).getTime();
                        if (!Number.isFinite(ts) || ts < windowStartMs || ts > nowMs) return;
                        const hour = Math.floor((ts - windowStartMs) / (60 * 60 * 1000));
                        if (hourlyData[hour] !== undefined) {
                            hourlyData[hour].total++;
                            if (h.status === 'up') hourlyData[hour].up++;
                            else if (h.status === 'down') hourlyData[hour].down++;
                            else if (h.status === 'slow') hourlyData[hour].slow++;
                        }
                    });

                    // Fill gaps for stable monitors
                    const fallbackStatus = site.status === 'up' || site.status === 'down' || site.status === 'slow' ? site.status : null;
                    const has24hSamples = Object.values(hourlyData).some(d => d.total > 0);
                    if (!has24hSamples && fallbackStatus) {
                        for (let h = 0; h < 24; h++) {
                            hourlyData[h].total = 1;
                            hourlyData[h][fallbackStatus] = 1;
                        }
                    } else {
                        let carryStatus = null;
                        for (let h = 0; h < 24; h++) {
                            const d = hourlyData[h];
                            if (d.total > 0) {
                                if (d.up >= d.down && d.up >= d.slow) carryStatus = 'up';
                                else if (d.down >= d.up && d.down >= d.slow) carryStatus = 'down';
                                else carryStatus = 'slow';
                                continue;
                            }
                            if (carryStatus) {
                                d.total = 1;
                                d[carryStatus] = 1;
                            }
                        }
                    }

                    // Build timeline bars
                    let timelineBars = '';
                    for (let h = 0; h < 24; h++) {
                        const data = hourlyData[h];
                        const x = (h / 24) * chartWidth;
                        const barWidth = (chartWidth / 24) - 2;

                        let color = '#6b7280'; // no data
                        let tooltip = 'Немає даних';

                        if (data.total > 0) {
                            const uptime = (data.up / data.total) * 100;
                            if (uptime >= 90) {
                                color = '#22c55e'; // up
                                tooltip = `UP: ${data.up}/${data.total}`;
                            } else if (uptime >= 50) {
                                color = '#eab308'; // slow
                                tooltip = `SLOW: ${data.slow}/${data.total}`;
                            } else {
                                color = '#ef4444'; // down
                                tooltip = `DOWN: ${data.down}/${data.total}`;
                            }
                        }

                        timelineBars += `<div style="position: absolute; left: ${x}px; width: ${barWidth}px; height: 100%; background: ${color}; border-radius: 2px; cursor: pointer;" title="${h}:00 - ${tooltip}"></div>`;
                    }

                    const statusColor = site.status === 'up' ? '#22c55e' : site.status === 'slow' ? '#eab308' : '#ef4444';
                    const hourValues = Object.values(hourlyData);
                    const samples = hourValues.reduce((acc, d) => acc + d.total, 0);
                    const upSamples = hourValues.reduce((acc, d) => acc + d.up, 0);
                    const uptime = samples > 0 ? ((upSamples / samples) * 100).toFixed(1) : 0;

                    siteCharts += `<div style="position: relative; padding: 10px 0; border-bottom: 1px solid var(--border);">
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                            <div style="width: 10px; height: 10px; border-radius: 50%; background: ${statusColor}; box-shadow: 0 0 8px ${statusColor};"></div>
                            <div style="flex: 1; min-width: 120px;">
                                <div style="font-size: 13px; font-weight: 500; color: var(--text-primary);">${site.name}</div>
                            </div>
                            <div style="min-width: 60px; text-align: right;">
                                <div style="font-size: 14px; font-weight: bold; color: ${uptime >= 99 ? '#22c55e' : uptime >= 95 ? '#eab308' : '#ef4444'};">${uptime}%</div>
                            </div>
                        </div>
                        <div style="position: relative; height: ${chartHeight}px; background: rgba(30, 41, 59, 0.5); border-radius: 6px; overflow: visible;">
                            <div style="position: absolute; top: -18px; left: 0; right: 0; height: 18px;">${timeLabels.join('')}</div>
                            ${hourMarkers.join('')}
                            <div style="position: absolute; left: ${nowX}px; top: 0; bottom: 0; width: 2px; background: #00d9ff; z-index: 10; box-shadow: 0 0 8px #00d9ff;"></div>
                            ${timelineBars}
                        </div>
                    </div>`;
                }

                container.innerHTML = `<div style="border-top: 1px solid var(--border); padding-top: 5px;">${siteCharts || '<div style="color: var(--text-secondary); padding: 20px; text-align: center;">Немає даних</div>'}</div>`;
            } catch(e) {
                console.error(e);
                container.innerHTML = '<div style="color: var(--text-secondary); padding: 40px;">Помилка завантаження</div>';
            }
        }

        function renderMonitors() {
            const grid = document.getElementById('dashboardMonitors');
            if (!grid) return;

            let filtered = currentFilter === 'all' ? sitesData : sitesData.filter(s => s.monitor_type === currentFilter);

            // Sort: DOWN first, then slow/paused, then UP
            filtered.sort((a, b) => {
                const statusOrder = { 'down': 0, 'slow': 1, 'paused': 2, 'unknown': 3, 'up': 4 };
                const orderA = statusOrder[a.status] ?? 5;
                const orderB = statusOrder[b.status] ?? 5;
                return orderA - orderB;
            });

            if (filtered.length === 0) {
                grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">Моніторів не знайдено.</div>';
                return;
            }

            let html = '';
            filtered.forEach(site => {
                const statusClass = site.status === 'up' ? 'up' : (site.status === 'paused' ? 'paused' : 'down');
                const statusText = site.status === 'up' ? 'UP' : (site.status === 'paused' ? 'PAUSED' : 'DOWN');
                const statusColor = site.status === 'up' ? 'var(--success)' : 'var(--danger)';
                const safeName = (site.name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const safeUrl = (site.url || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

                html += `
                <div class="monitor-card ${statusClass}" data-id="${site.id}" data-name="${safeName}" data-url="${safeUrl}">
                    <div class="monitor-header">
                        <div style="min-width: 0; flex: 1;">
                            <div class="monitor-name" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${safeName}">${site.name}</div>
                            <div class="monitor-url" title="${safeUrl}">${site.url}</div>
                        </div>
                        <span class="monitor-type-badge">${site.monitor_type}</span>
                    </div>
                    <div class="monitor-stats">
                        <div class="monitor-stat"><div class="monitor-stat-value" style="color:${statusColor}">${statusText}</div><div class="monitor-stat-label">Status</div></div>
                        <div class="monitor-stat"><div class="monitor-stat-value">${site.response_time || '—'}ms</div><div class="monitor-stat-label">Time</div></div>
                        <div class="monitor-stat"><div class="monitor-stat-value">${site.uptime || 100}%</div><div class="monitor-stat-label">Uptime</div></div>
                        <div class="monitor-stat"><div class="monitor-stat-value">${site.status_code || '—'}</div><div class="monitor-stat-label">HTTP</div></div>
                    </div>
                    <div class="monitor-actions">
                        <button class="btn btn-check" onclick="checkSite(${site.id})">Check</button>
                        <button class="btn btn-edit" onclick="openEditModal(${site.id}, '${safeName}', '${encodeURIComponent(safeUrl)}', '${encodeURIComponent(JSON.stringify(site.notify_methods || []))}')">Edit</button>
                        <button class="btn btn-delete" onclick="deleteSite(${site.id})">Delete</button>
                    </div>
                </div>`;
            });
            grid.innerHTML = html;
        }

        async function checkSite(id) {
            try {
                await fetch(`/api/sites/${id}/check`, { method: 'POST' });
                loadSites();
            } catch(e) { console.error(e); }
        }

        async function deleteSite(id) {
            if (!confirm('Ви впевнені, що хочете видалити цей монітор?')) return;
            try {
                await fetch(`/api/sites/${id}`, { method: 'DELETE' });
                loadSites();
            } catch(e) { console.error(e); }
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.querySelector(`.tab-btn[onclick="switchTab('${tabId}')"]`).classList.add('active');

            if (tabId === 'dashboard') { loadSites(); loadUptimeChart(); }
            if (tabId === 'ssl') loadSSLCertificates();
            if (tabId === 'incidents') loadIncidents();
        }

        // Auto-refresh incidents every 30 seconds
        let incidentsRefreshInterval = null;

        function startIncidentsAutoRefresh() {
            if (incidentsRefreshInterval) clearInterval(incidentsRefreshInterval);
            incidentsRefreshInterval = setInterval(() => {
                const incidentsTab = document.getElementById('tab-incidents');
                if (incidentsTab && incidentsTab.classList.contains('active')) {
                    loadIncidents();
                }
            }, 30000); // 30 seconds
        }

        async function addSite() {
            const name = document.getElementById('siteName').value;
            const url = document.getElementById('siteUrl').value;
            const monitor_type = document.getElementById('monitorType').value;
            const container = document.getElementById('siteNotifyOptions');
            const notify_methods = container ? Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(o => o.value) : [];

            if (!name || !url) return alert('Заповніть назву та URL');

            try {
                const response = await fetch('/api/sites', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, url, monitor_type, notify_methods})
                });
                if (response.ok) {
                    document.getElementById('siteName').value = '';
                    document.getElementById('siteUrl').value = '';
                    if (container) container.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                    loadSites();
                    alert('Монітор додано!');
                }
            } catch(e) { console.error(e); }
        }

        async function loadSSLCertificates() {
            try {
                const response = await fetch('/api/ssl-certificates');
                sslCertificatesData = await response.json();
                renderSSLCertificates();
            } catch(e) { console.error(e); }
        }

        function renderSSLCertificates() {
            const grid = document.getElementById('sslGrid');
            if (!grid) return;
            if (sslCertificatesData.length === 0) {
                grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;">Немає SSL даних.</div>';
                return;
            }
            let html = '';
            sslCertificatesData.forEach(cert => {
                const days = cert.days_until_expire;
                const statusColor = days <= 0 ? 'var(--danger)' : days <= 7 ? 'var(--warning)' : 'var(--success)';
                html += `
                <div class="ssl-card" style="padding: 12px; background: rgba(30, 41, 59, 0.4); border-radius: 10px; border-left: 4px solid ${statusColor}; border: 1px solid rgba(148, 163, 184, 0.1); margin-bottom: 10px; overflow: hidden;">
                    <div style="font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${cert.site_name}">${cert.site_name}</div>
                    <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${cert.hostname}">${cert.hostname}</div>
                    <div style="display: flex; justify-content: space-between; font-size: 12px;">
                        <span>Term: ${days} days</span>
                        <span style="color: ${statusColor}">${days <= 0 ? '❌ Overdue' : '✅ Valid'}</span>
                    </div>
                </div>`;
            });
            grid.innerHTML = html;
        }

        let responseTimeData = [];
        let incidentsData = [];

        async function loadDashboard() {
            loadSites();
            loadUptimeChart();
            loadSSLCertificates();
            await loadResponseTimeStats();
            await loadIncidents();
        }

        async function loadResponseTimeStats() {
            try {
                const response = await fetch('/api/stats/response-time');
                responseTimeData = await response.json();
                renderResponseTimeChart();
            } catch(e) { console.error(e); }
        }

        function renderResponseTimeChart() {
            const canvas = document.getElementById('responseTimeChart');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const data = responseTimeData;

            if (data.length === 0) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#6b7280';
                ctx.font = '14px Inter';
                ctx.textAlign = 'center';
                ctx.fillText('Немає даних про час відповіді', canvas.width / 2, canvas.height / 2);
                return;
            }

            canvas.width = canvas.parentElement?.clientWidth || 600;
            canvas.height = 250;

            const maxTime = Math.max(...data.map(d => d.max_time), 100);
            const barWidth = (canvas.width - 60) / data.length - 10;
            const scale = (canvas.height - 60) / maxTime;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            data.forEach((item, i) => {
                const x = 40 + i * (barWidth + 10);
                const avgHeight = item.avg_time * scale;
                const maxHeight = item.max_time * scale;

                ctx.fillStyle = 'rgba(0, 217, 255, 0.3)';
                ctx.fillRect(x, canvas.height - 40 - maxHeight, barWidth, maxHeight);

                ctx.fillStyle = '#00d9ff';
                ctx.fillRect(x, canvas.height - 40 - avgHeight, barWidth, avgHeight);

                ctx.fillStyle = '#9ca3af';
                ctx.font = '10px Inter';
                ctx.textAlign = 'center';
                const name = item.site_name.length > 10 ? item.site_name.substring(0, 10) + '...' : item.site_name;
                ctx.fillText(name, x + barWidth / 2, canvas.height - 10);

                ctx.fillStyle = '#00d9ff';
                ctx.font = '11px Inter';
                ctx.fillText(Math.round(item.avg_time) + 'ms', x + barWidth / 2, canvas.height - 45 - avgHeight);
            });
        }

        async function loadIncidents() {
            try {
                const response = await fetch('/api/incidents');
                incidentsData = await response.json();
                renderIncidents();
                updateIncidentsCount();
            } catch(e) { console.error(e); }
        }

        function updateIncidentsCount() {
            const el = document.querySelector('#tab-dashboard .hero-stat-value[style*="var(--warning)"]');
            if (el) {
                el.textContent = incidentsData.length;
            }
        }

        function renderIncidents() {
            const list = document.getElementById('incidentsList');
            if (!list) return;

            if (incidentsData.length === 0) {
                list.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Немає інцидентів - всі монітори працюють!</div>';
                return;
            }

            let html = '<div style="display: flex; flex-direction: column; gap: 12px;">';
            incidentsData.forEach(inc => {
                const date = new Date(inc.checked_at).toLocaleString('uk-UA');
                const isDown = inc.status === 'down';
                const isSlow = inc.status === 'slow';
                const bgColor = isDown ? 'rgba(239, 68, 68, 0.15)' : isSlow ? 'rgba(234, 179, 8, 0.15)' : 'rgba(34, 197, 94, 0.1)';
                const borderColor = isDown ? '#ef4444' : isSlow ? '#eab308' : '#22c55e';
                const statusText = isDown ? '🔴 DOWN' : isSlow ? '🟡 SLOW' : '🟢 UP';
                const prevText = inc.prev_status ? ` (було: ${inc.prev_status.toUpperCase()})` : '';

                html += `
                <div style="background: ${bgColor}; border-left: 4px solid ${borderColor}; padding: 16px; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                                <span style="font-weight: 600; font-size: 15px; color: var(--text-primary);">${inc.site_name}</span>
                                <span style="font-size: 12px; padding: 2px 8px; background: ${borderColor}22; border-radius: 4px; color: ${borderColor};">${statusText}</span>
                            </div>
                            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">${inc.site_url}</div>
                            ${inc.duration ? `<div style="font-size: 12px; color: ${isDown ? '#ef4444' : '#eab308'}; font-weight: 500; margin-bottom: 4px;">⏱️ Тривалість: ${inc.duration}</div>` : ''}
                            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 6px;">
                                <span>🕐 ${date}</span>
                                ${inc.response_time ? `<span style="margin-left: 12px;">⚡ ${Math.round(inc.response_time)}ms</span>` : ''}
                                ${inc.status_code ? `<span style="margin-left: 12px;">📄 HTTP ${inc.status_code}</span>` : ''}
                            </div>
                        </div>
                    </div>
                    ${inc.error_message ? `<div style="font-size: 12px; color: #ef4444; margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.2); border-radius: 4px; font-family: monospace;">${inc.error_message}</div>` : ''}
                </div>`;
            });
            html += '</div>';
            list.innerHTML = html;
        }

        async function checkAllMonitors() {
            try {
                for (const site of sitesData) {
                    await fetch(`/api/sites/${site.id}/check`, { method: 'POST' });
                }
                loadSites();
            } catch(e) { console.error(e); }
        }

        function initNotifyUI() {
            ['telegram', 'teams', 'discord', 'slack', 'email', 'sms'].forEach(method => {
                const config = notifyConfig[method] || {};
                const card = document.getElementById('card-' + method);
                const toggle = document.getElementById('toggle-' + method);
                if (!card || !toggle) return;
                if (config.enabled) {
                    card.classList.add('enabled');
                    toggle.checked = true;
                }
                const fields = card.querySelectorAll('input[type="text"], input[type="password"]');
                fields.forEach(input => {
                    const fieldName = input.id.replace(method + '-', '').replace(/-/g, '_');
                    if (config[fieldName] !== undefined) input.value = config[fieldName];
                });
            });
        }

        function toggleNotify(method) {
            const card = document.getElementById('card-' + method);
            const toggle = document.getElementById('toggle-' + method);
            if (!card || !toggle) return;
            if (toggle.checked) card.classList.add('enabled');
            else card.classList.remove('enabled');
        }

        function updateChannelFields() {
            const method = document.getElementById('addChannelMethod').value;
            if (method === 'telegram') {
                document.getElementById('telegramFields').style.display = 'block';
                document.getElementById('webhookFields').style.display = 'none';
                document.getElementById('emailFields').style.display = 'none';
            } else if (method === 'email') {
                document.getElementById('telegramFields').style.display = 'none';
                document.getElementById('webhookFields').style.display = 'none';
                document.getElementById('emailFields').style.display = 'block';
            } else {
                document.getElementById('telegramFields').style.display = 'none';
                document.getElementById('webhookFields').style.display = 'block';
                document.getElementById('emailFields').style.display = 'none';
            }
        }

        function openAddChannelModal(method) {
            document.getElementById('addChannelMethod').value = method;
            document.getElementById('newChannelName').value = '';
            document.getElementById('newTelegramToken').value = '';
            document.getElementById('newTelegramChatId').value = '';
            document.getElementById('newWebhookUrl').value = '';
            document.getElementById('newEmailSmtp').value = '';
            document.getElementById('newEmailPort').value = '';
            document.getElementById('newEmailUser').value = '';
            document.getElementById('newEmailPass').value = '';
            document.getElementById('newEmailTo').value = '';

            if (method === 'telegram') {
                document.getElementById('telegramFields').style.display = 'block';
                document.getElementById('webhookFields').style.display = 'none';
                document.getElementById('emailFields').style.display = 'none';
            } else if (method === 'email') {
                document.getElementById('telegramFields').style.display = 'none';
                document.getElementById('webhookFields').style.display = 'none';
                document.getElementById('emailFields').style.display = 'block';
            } else {
                document.getElementById('telegramFields').style.display = 'none';
                document.getElementById('webhookFields').style.display = 'block';
                document.getElementById('emailFields').style.display = 'none';
            }
            document.getElementById('addChannelModal').classList.add('active');
        }

        function closeAddChannelModal() {
            document.getElementById('addChannelModal').classList.remove('active');
        }

        function addNewChannel() {
            const method = document.getElementById('addChannelMethod').value;
            const name = document.getElementById('newChannelName').value.trim();
            if (!name) return alert('Введіть назву каналу!');

            const channelId = 'ch_' + Date.now();
            let html = '';

            if (method === 'telegram') {
                const token = document.getElementById('newTelegramToken').value.trim();
                const chat_id = document.getElementById('newTelegramChatId').value.trim();
                if (!token || !chat_id) return alert('Введіть token та chat_id!');

                html = `<div class="channel-item" id="ch_${channelId}">
                    <div class="channel-header">
                        <span class="channel-name">📱 ${name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('${method}', '${channelId}')">✕</button>
                    </div>
                    <input type="hidden" name="${method}_channels" value="${channelId}">
                    <input type="hidden" id="${method}_${channelId}_name" value="${name}">
                    <input type="hidden" id="${method}_${channelId}_token" value="${token}">
                    <input type="hidden" id="${method}_${channelId}_chat_id" value="${chat_id}">
                </div>`;
            } else if (method === 'email') {
                const smtp_server = document.getElementById('newEmailSmtp').value.trim();
                const smtp_port = document.getElementById('newEmailPort').value.trim();
                const username = document.getElementById('newEmailUser').value.trim();
                const password = document.getElementById('newEmailPass').value.trim();
                const to_email = document.getElementById('newEmailTo').value.trim();
                if (!smtp_server || !username || !to_email) return alert('Заповніть всі поля!');

                html = `<div class="channel-item" id="ch_${channelId}">
                    <div class="channel-header">
                        <span class="channel-name">📧 ${name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('${method}', '${channelId}')">✕</button>
                    </div>
                    <input type="hidden" name="${method}_channels" value="${channelId}">
                    <input type="hidden" id="${method}_${channelId}_name" value="${name}">
                    <input type="hidden" id="${method}_${channelId}_smtp_server" value="${smtp_server}">
                    <input type="hidden" id="${method}_${channelId}_smtp_port" value="${smtp_port || 587}">
                    <input type="hidden" id="${method}_${channelId}_username" value="${username}">
                    <input type="hidden" id="${method}_${channelId}_password" value="${password}">
                    <input type="hidden" id="${method}_${channelId}_to_email" value="${to_email}">
                </div>`;
            } else {
                const webhookUrl = document.getElementById('newWebhookUrl').value.trim();
                if (!webhookUrl) return alert('Введіть URL webhook!');

                html = `<div class="channel-item" id="ch_${channelId}">
                    <div class="channel-header">
                        <span class="channel-name">🔗 ${name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('${method}', '${channelId}')">✕</button>
                    </div>
                    <input type="hidden" name="${method}_channels" value="${channelId}">
                    <input type="hidden" id="${method}_${channelId}_name" value="${name}">
                    <input type="hidden" id="${method}_${channelId}_webhook_url" value="${webhookUrl}">
                </div>`;
            }

            document.getElementById('channels-' + method).insertAdjacentHTML('beforeend', html);
            document.getElementById('newTelegramToken').value = '';
            document.getElementById('newTelegramChatId').value = '';
            document.getElementById('newWebhookUrl').value = '';
            document.getElementById('newEmailSmtp').value = '';
            document.getElementById('newEmailPort').value = '';
            document.getElementById('newEmailUser').value = '';
            document.getElementById('newEmailPass').value = '';
            document.getElementById('newEmailTo').value = '';
            closeAddChannelModal();
        }

        function removeChannel(method, channelId) {
            const el = document.getElementById('ch_' + channelId);
            if (el) el.remove();
        }

        async function saveNotifySettings() {
            const settings = {
                telegram: { enabled: document.getElementById('toggle-telegram')?.checked, channels: [] },
                discord: { enabled: document.getElementById('toggle-discord')?.checked, channels: [] },
                teams: { enabled: document.getElementById('toggle-teams')?.checked, channels: [] },
                email: { enabled: document.getElementById('toggle-email')?.checked, channels: [] },
            };

            ['telegram', 'discord', 'teams', 'email'].forEach(method => {
                const container = document.getElementById('channels-' + method);
                if (container) {
                    const items = container.querySelectorAll('.channel-item');
                    items.forEach(item => {
                        const id = item.id.replace('ch_', '');
                        const name = document.getElementById(`${method}_${id}_name`)?.value;
                        if (method === 'telegram') {
                            const token = document.getElementById(`${method}_${id}_token`)?.value;
                            const chat_id = document.getElementById(`${method}_${id}_chat_id`)?.value;
                            if (name && token && chat_id) {
                                settings[method].channels.push({ id, name, token, chat_id });
                            }
                        } else if (method === 'email') {
                            const smtp_server = document.getElementById(`${method}_${id}_smtp_server`)?.value;
                            const smtp_port = document.getElementById(`${method}_${id}_smtp_port`)?.value || 587;
                            const username = document.getElementById(`${method}_${id}_username`)?.value;
                            const password = document.getElementById(`${method}_${id}_password`)?.value;
                            const to_email = document.getElementById(`${method}_${id}_to_email`)?.value;
                            if (name && smtp_server && username && to_email) {
                                settings[method].channels.push({ id, name, smtp_server, smtp_port: parseInt(smtp_port), username, password, to_email });
                            }
                        } else {
                            const webhook_url = document.getElementById(`${method}_${id}_webhook_url`)?.value;
                            if (name && webhook_url) {
                                settings[method].channels.push({ id, name, webhook_url });
                            }
                        }
                    });
                }
            });

            try {
                await fetch('/api/notify-settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings) });
                alert('✅ Налаштування збережено!');
            } catch(e) { console.error(e); }
        }

        async function loadAppSettings() {
            try {
                const response = await fetch('/api/app-settings');
                const data = await response.json();
                const el = document.getElementById('displayAddress');
                if (el) el.value = data.display_address || '';
            } catch(e) { /* ignore */ }
        }

        async function saveAddress() {
            const addr = document.getElementById('displayAddress')?.value || '';
            try {
                await fetch('/api/app-settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({display_address: addr}) });
                alert('✅ Адресу збережено!');
            } catch(e) { console.error(e); }
        }

        function openEditModal(id, name, url, notifyMethods) {
            document.getElementById('editSiteId').value = id;
            document.getElementById('editSiteName').value = name;
            document.getElementById('editSiteUrl').value = decodeURIComponent(url);
            const methods = typeof notifyMethods === 'string' ? JSON.parse(decodeURIComponent(notifyMethods)) : notifyMethods;
            const container = document.getElementById('editSiteNotify');
            if (container) {
                container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                    cb.checked = methods.includes(cb.value);
                });
            }
            document.getElementById('editModal').classList.add('active');
        }

        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }

        async function saveEdit() {
            const id = document.getElementById('editSiteId').value;
            const name = document.getElementById('editSiteName').value.trim();
            const url = document.getElementById('editSiteUrl').value.trim();
            const container = document.getElementById('editSiteNotify');
            const notify_methods = container ? Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(o => o.value) : [];
            if (!name || !url) return alert('Заповніть всі поля!');
            try {
                await fetch(`/api/sites/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, url, notify_methods}) });
                closeEditModal();
                loadSites();
            } catch(e) { console.error(e); }
        }

        async function checkSSLCertificates() {
            try {
                await fetch('/api/ssl-certificates/check', { method: 'POST' });
                loadSSLCertificates();
            } catch(e) { console.error(e); }
        }
"""


def get_notification_cards_html(config):
    methods = [
        ("telegram", "📱", "Telegram", "Миттєві сповіщення"),
        ("discord", "🎮", "Discord", "Геймерські спільноти"),
        ("teams", "🏢", "MS Teams", "Робочі групи"),
        ("email", "📧", "Email", "Електронна пошта"),
    ]

    html = ""
    for key, icon, name, desc in methods:
        enabled = config.get(key, {}).get("enabled", False)
        enabled_class = "enabled" if enabled else ""
        checked = "checked" if enabled else ""

        channels = config.get(key, {}).get("channels", [])

        channels_html = ""
        for ch in channels:
            ch_id = ch.get("id", "")
            ch_name = ch.get("name", "Канал")
            if key == "telegram":
                channels_html += f"""
                <div class="channel-item" id="ch_{ch_id}">
                    <div class="channel-header">
                        <span class="channel-name">📱 {ch_name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('{key}', '{ch_id}')">✕</button>
                    </div>
                    <input type="hidden" name="{key}_channels" value="{ch_id}">
                    <input type="hidden" id="{key}_{ch_id}_name" value="{ch_name}">
                    <input type="hidden" id="{key}_{ch_id}_token" value="{ch.get("token", "")}">
                    <input type="hidden" id="{key}_{ch_id}_chat_id" value="{ch.get("chat_id", "")}">
                </div>"""
            elif key == "email":
                channels_html += f"""
                <div class="channel-item" id="ch_{ch_id}">
                    <div class="channel-header">
                        <span class="channel-name">📧 {ch_name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('{key}', '{ch_id}')">✕</button>
                    </div>
                    <input type="hidden" name="{key}_channels" value="{ch_id}">
                    <input type="hidden" id="{key}_{ch_id}_name" value="{ch_name}">
                    <input type="hidden" id="{key}_{ch_id}_smtp_server" value="{ch.get("smtp_server", "")}">
                    <input type="hidden" id="{key}_{ch_id}_smtp_port" value="{ch.get("smtp_port", 587)}">
                    <input type="hidden" id="{key}_{ch_id}_username" value="{ch.get("username", "")}">
                    <input type="hidden" id="{key}_{ch_id}_password" value="{ch.get("password", "")}">
                    <input type="hidden" id="{key}_{ch_id}_to_email" value="{ch.get("to_email", "")}">
                </div>"""
            else:
                channels_html += f"""
                <div class="channel-item" id="ch_{ch_id}">
                    <div class="channel-header">
                        <span class="channel-name">🔗 {ch_name}</span>
                        <button type="button" class="btn-remove-channel" onclick="removeChannel('{key}', '{ch_id}')">✕</button>
                    </div>
                    <input type="hidden" name="{key}_channels" value="{ch_id}">
                    <input type="hidden" id="{key}_{ch_id}_name" value="{ch_name}">
                    <input type="hidden" id="{key}_{ch_id}_webhook_url" value="{ch.get("webhook_url", "")}">
                </div>"""

        if key == "email":
            card = f"""
            <div class="notify-card {enabled_class}" id="card-{key}">
                <div class="notify-header">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:24px;">{icon}</span>
                        <div><div style="font-weight:600;">{name}</div><div style="font-size:12px; color:var(--text-secondary);">{desc}</div></div>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="toggle-{key}" onchange="toggleNotify('{key}')" {checked}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="channels-list" id="channels-{key}">
                    {channels_html}
                </div>
                <button type="button" class="btn-add-channel-inline" onclick="openAddChannelModal('{key}')">➕ Додати канал</button>
            </div>"""
        else:
            card = f"""
            <div class="notify-card {enabled_class}" id="card-{key}">
                <div class="notify-header">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:24px;">{icon}</span>
                        <div><div style="font-weight:600;">{name}</div><div style="font-size:12px; color:var(--text-secondary);">{desc}</div></div>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="toggle-{key}" onchange="toggleNotify('{key}')" {checked}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="channels-list" id="channels-{key}">
                    {channels_html}
                </div>
                <button type="button" class="btn-add-channel-inline" onclick="openAddChannelModal('{key}')">➕ Додати канал</button>
            </div>"""

        html += card
    return html


def get_dashboard_html(
    total_sites, up_sites, down_sites, notify_config_json, notification_cards
):
    return DASHBOARD_HTML.format(
        total_sites=total_sites,
        up_sites=up_sites,
        down_sites=down_sites,
        notify_config_json=notify_config_json,
        notification_cards=notification_cards,
        js_functions=DASHBOARD_JS,
    )


def get_public_status_html(
    overall_status_class,
    overall_status_text,
    total,
    up_count,
    down_count,
    monitors_html,
    timestamp,
):
    return PUBLIC_STATUS_HTML.format(
        overall_status_class=overall_status_class,
        overall_status_text=overall_status_text,
        total=total,
        up_count=up_count,
        down_count=down_count,
        monitors_html=monitors_html,
        timestamp=timestamp,
    )


def get_users_html():
    """User management page HTML"""
    return USERS_PAGE_HTML


USERS_PAGE_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Користувачі - Uptime Monitor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #0f0f23);
            padding: 20px 40px;
            border-bottom: 1px solid #2a2a4a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { font-size: 24px; font-weight: 700; }
        .logo-icon {
            display: inline-block;
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #00d9ff, #00ff88);
            border-radius: 10px;
            line-height: 40px;
            font-size: 20px;
            margin-right: 10px;
            text-align: center;
        }
        .nav-links a {
            color: #a0a0b0;
            text-decoration: none;
            margin-left: 20px;
            font-size: 14px;
            transition: color 0.3s;
        }
        .nav-links a:hover { color: #00d9ff; }
        .container { max-width: 1000px; margin: 0 auto; padding: 40px; }
        h1 { font-size: 28px; margin-bottom: 30px; }

        .card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid #2a2a4a;
        }

        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #00d9ff, #00a8cc);
            color: #000;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4);
        }
        .btn-danger {
            background: linear-gradient(135deg, #ff4757, #ff3838);
            color: #fff;
        }
        .btn-danger:hover {
            box-shadow: 0 5px 20px rgba(255, 71, 87, 0.4);
        }
        .btn-sm { padding: 6px 12px; font-size: 12px; }

        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid #2a2a4a; }
        th { color: #a0a0b0; font-weight: 500; font-size: 13px; }
        td { font-size: 14px; }
        tr:hover { background: rgba(255,255,255,0.02); }

        .role-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .role-admin {
            background: rgba(0, 217, 255, 0.15);
            color: #00d9ff;
        }
        .role-viewer {
            background: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 15px;
            width: 100%;
            max-width: 400px;
            border: 1px solid #2a2a4a;
        }
        .modal-header {
            font-size: 20px;
            margin-bottom: 20px;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #a0a0b0;
            font-size: 13px;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            font-size: 14px;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        .modal-actions .btn { flex: 1; }
        .btn-secondary {
            background: #2a2a4a;
            color: #fff;
        }

        .actions-cell { display: flex; gap: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo"><span class="logo-icon">⚡</span>Uptime Monitor</div>
        <div class="nav-links">
            <a href="/">Дашборд</a>
            <a href="/users">Користувачі</a>
            <a href="/logout">Вийти</a>
        </div>
    </div>

    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <h1>Управління користувачами</h1>
            <button class="btn btn-primary" onclick="showCreateModal()">+ Додати користувача</button>
        </div>

        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Created</th>
                        <th>Last Login</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="usersTableBody">
                    <tr><td colspan="6" style="text-align: center; color: #a0a0b0;">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Create User Modal -->
    <div class="modal" id="createModal">
        <div class="modal-content">
            <div class="modal-header">Додати користувача</div>
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="newUsername" placeholder="Enter username">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="newPassword" placeholder="Enter password">
            </div>
            <div class="form-group">
                <label>Role</label>
                <select id="newRole">
                    <option value="viewer">Viewer (read-only)</option>
                    <option value="admin">Admin</option>
                </select>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('createModal')">Cancel</button>
                <button class="btn btn-primary" onclick="createUser()">Create</button>
            </div>
        </div>
    </div>

    <!-- Edit User Modal -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">Редагувати користувача</div>
            <input type="hidden" id="editUsername">
            <div class="form-group">
                <label>Role</label>
                <select id="editRole">
                    <option value="viewer">Viewer (read-only)</option>
                    <option value="admin">Admin</option>
                </select>
            </div>
            <div class="form-group">
                <label>New Password (optional)</label>
                <input type="password" id="editPassword" placeholder="Leave empty to keep current">
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('editModal')">Cancel</button>
                <button class="btn btn-primary" onclick="updateUser()">Save</button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;

        // Load users on page load
        loadUsers();
        loadCurrentUser();

        async function loadCurrentUser() {
            try {
                const res = await fetch('/api/user');
                if (res.ok) {
                    currentUser = await res.json();
                    if (!currentUser.is_admin) {
                        window.location.href = '/';
                    }
                } else {
                    window.location.href = '/login';
                }
            } catch (e) {
                console.error('Error loading current user:', e);
            }
        }

        async function loadUsers() {
            try {
                const res = await fetch('/api/users');
                if (!res.ok) {
                    document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="6" style="text-align: center; color: #ff4757;">Error loading users</td></tr>';
                    return;
                }
                const users = await res.json();
                renderUsers(users);
            } catch (e) {
                document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="6" style="text-align: center; color: #ff4757;">Error loading users</td></tr>';
            }
        }

        function renderUsers(users) {
            const tbody = document.getElementById('usersTableBody');
            if (users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #a0a0b0;">No users found</td></tr>';
                return;
            }

            tbody.innerHTML = users.map(user => `
                <tr>
                    <td>${user.id}</td>
                    <td>${user.username}</td>
                    <td><span class="role-badge ${user.role === 'admin' ? 'role-admin' : 'role-viewer'}">${user.role}</span></td>
                    <td>${formatDate(user.created_at)}</td>
                    <td>${user.last_login ? formatDate(user.last_login) : 'Never'}</td>
                    <td>
                        <div class="actions-cell">
                            <button class="btn btn-sm btn-secondary" onclick="showEditModal('${user.username}', '${user.role}')">Edit</button>
                            ${user.username !== currentUser?.username ? `<button class="btn btn-sm btn-danger" onclick="deleteUser('${user.username}')">Delete</button>` : ''}
                        </div>
                    </td>
                </tr>
            `).join('');
        }

        function formatDate(dateStr) {
            if (!dateStr) return 'Never';
            try {
                const date = new Date(dateStr);
                return date.toLocaleDateString('uk-UA', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch {
                return dateStr;
            }
        }

        function showCreateModal() {
            document.getElementById('newUsername').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('newRole').value = 'viewer';
            document.getElementById('createModal').classList.add('active');
        }

        function showEditModal(username, role) {
            document.getElementById('editUsername').value = username;
            document.getElementById('editRole').value = role;
            document.getElementById('editPassword').value = '';
            document.getElementById('editModal').classList.add('active');
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }

        async function createUser() {
            const username = document.getElementById('newUsername').value.trim();
            const password = document.getElementById('newPassword').value;
            const role = document.getElementById('newRole').value;

            if (!username || !password) {
                alert('Username and password are required');
                return;
            }

            try {
                const res = await fetch('/api/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, role })
                });

                const data = await res.json();
                if (res.ok) {
                    alert(data.message);
                    closeModal('createModal');
                    loadUsers();
                } else {
                    alert(data.detail || 'Error creating user');
                }
            } catch (e) {
                alert('Error creating user');
            }
        }

        async function updateUser() {
            const username = document.getElementById('editUsername').value;
            const role = document.getElementById('editRole').value;
            const password = document.getElementById('editPassword').value;

            try {
                const body = { role };
                if (password) body.password = password;

                const res = await fetch(`/api/users/${username}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });

                const data = await res.json();
                if (res.ok) {
                    alert(data.message);
                    closeModal('editModal');
                    loadUsers();
                } else {
                    alert(data.detail || 'Error updating user');
                }
            } catch (e) {
                alert('Error updating user');
            }
        }

        async function deleteUser(username) {
            if (!confirm(`Are you sure you want to delete user "${username}"?`)) return;

            try {
                const res = await fetch(`/api/users/${username}`, {
                    method: 'DELETE'
                });

                const data = await res.json();
                if (res.ok) {
                    alert(data.message);
                    loadUsers();
                } else {
                    alert(data.detail || 'Error deleting user');
                }
            } catch (e) {
                alert('Error deleting user');
            }
        }
    </script>
</body>
</html>"""
