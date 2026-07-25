/**
 * Cron Flow Visualization — Hermes Cron Job Flow Visualizer
 *
 * A Hermes WebUI dashboard plugin that shows a flow diagram for each cron job:
 * the trigger, agent/script, connected APIs, file operations, and delivery target.
 *
 * ── Adding custom job profiles ──
 * Add entries to the CUSTOM_PROFILES object below. Each key is a job ID (from
 * your Hermes cron list) and the value is a profile object with "connections"
 * and "process" arrays. See EXAMPLE_PROFILES for the shape.
 *
 * Profile format:
 * {
 *   connections: [
 *     { type: 'api'|'file', label: 'Display name', detail: 'Description',
 *       direction: 'read'|'write', auth: 'API key type or null' }
 *   ],
 *   process: [
 *     { label: 'Step name', detail: 'What this step does' }
 *   ]
 * }
 *
 * The "connections" array appears in the 🔗 Known Connections grid.
 * The "process" array renders as a vertical flow diagram of ⚙️ steps.
 */
(function () {
  'use strict';

  // ══════════════════════════════════════════════════════════
  //  CUSTOM PROFILES — Add your own job profiles here
  // ══════════════════════════════════════════════════════════
  // Each key must match a cron job ID from your Hermes instance.
  // Run `hermes cron list` or check the WebUI Settings → Cron to find job IDs.
  var CUSTOM_PROFILES = {};

  // ══════════════════════════════════════════════════════════
  //  EXAMPLE PROFILES (read-only reference for the format)
  // ══════════════════════════════════════════════════════════
  // Copy these into CUSTOM_PROFILES above and adapt to your own jobs.
  // All example data is fictional — none of these jobs exist.
  var EXAMPLE_PROFILES = {
    'demo-daily-report': {
      name: 'Daily Report (example)',
      connections: [
        {
          type: 'api',
          label: 'Weather API',
          detail: 'GET current conditions for location',
          direction: 'read',
          auth: 'API key',
        },
        {
          type: 'api',
          label: 'Internal Analytics',
          detail: 'GET yesterday metrics',
          direction: 'read',
          auth: 'Bearer token',
        },
        {
          type: 'file',
          label: 'Report template',
          detail: '~/.hermes/templates/daily.md',
          format: 'Markdown',
        },
      ],
      process: [
        { label: '1. Fetch weather', detail: 'Open-Meteo or wttr.in for location' },
        { label: '2. Fetch metrics', detail: 'Internal API — daily active users, revenue, errors' },
        { label: '3. Render report', detail: 'Fill markdown template with fetched data' },
        {
          label: '4. Deliver',
          detail: 'Send via configured delivery channel (Slack/Telegram/WhatsApp)',
        },
      ],
    },
    'demo-data-pipeline': {
      name: 'Data Pipeline (example)',
      connections: [
        {
          type: 'api',
          label: 'Source API',
          detail: 'GET raw data, paginated',
          direction: 'read',
          auth: 'OAuth2',
        },
        {
          type: 'file',
          label: 'SQLite DB',
          detail: '~/.hermes/data/pipeline.db',
          format: 'SQLite',
        },
        {
          type: 'api',
          label: 'Destination API',
          detail: 'POST transformed data',
          direction: 'write',
          auth: 'API key',
        },
      ],
      process: [
        { label: '1. Extract', detail: 'Fetch latest records from source API (since last run)' },
        { label: '2. Transform', detail: 'Normalize fields, convert currencies, validate schema' },
        { label: '3. Load', detail: 'Upsert into local SQLite + POST to destination API' },
        { label: '4. Cleanup', detail: 'Archive state cursor, remove temp files' },
      ],
    },
  };

  // ══════════════════════════════════════════════════════════
  //  STYLES
  // ══════════════════════════════════════════════════════════
  var styles = document.createElement('style');
  styles.textContent = `
    :root {
      --bg: #0f1117;
      --card: #1a1d2e;
      --border: #2a2d3e;
      --text: #e1e4ea;
      --muted: #8b8fa3;
      --primary: #6366f1;
      --green: #22c55e;
      --blue: #3b82f6;
      --amber: #f59e0b;
      --red: #ef4444;
      --purple: #a855f7;
      --cyan: #06b6d4;
      --orange: #f97316;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 20px;
      line-height: 1.5;
      min-height: 100vh;
    }
    h1 { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
    h1 small { font-weight: 400; font-size: 13px; color: var(--muted); }

    .job-list { display: flex; flex-direction: column; gap: 6px; }
    .job-item {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .job-item:hover { border-color: var(--primary); background: #1e2040; }
    .job-item.active { border-color: var(--primary); background: #1e2040; }
    .job-icon {
      width: 32px; height: 32px;
      border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
      flex-shrink: 0;
    }
    .job-icon.agent { background: rgba(99,102,241,0.15); color: var(--primary); }
    .job-icon.script { background: rgba(6,182,212,0.15); color: var(--cyan); }
    .job-icon.hybrid { background: rgba(245,158,11,0.15); color: var(--amber); }
    .job-info { flex: 1; min-width: 0; }
    .job-name { font-size: 13px; font-weight: 600; }
    .job-meta { font-size: 11px; color: var(--muted); margin-top: 2px; display: flex; flex-wrap: wrap; gap: 6px; }
    .job-meta .chip {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 1px 6px;
      font-family: 'SF Mono', monospace;
      font-size: 10px;
    }
    .job-arrow { color: var(--muted); font-size: 14px; flex-shrink: 0; }

    .flow-section { margin-top: 24px; }
    .flow-section h2 { font-size: 15px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }

    .flow-diagram {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0;
    }
    .flow-node {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 16px;
      min-width: 240px;
      max-width: 360px;
      text-align: center;
    }
    .flow-node .icon { font-size: 16px; }
    .flow-node .title { font-size: 13px; font-weight: 600; margin-top: 2px; word-break: break-word; }
    .flow-node .sub { font-size: 11px; color: var(--muted); margin-top: 1px; font-family: 'SF Mono', monospace; word-break: break-all; }
    .flow-node.cron { border-color: var(--primary); background: linear-gradient(135deg, var(--card), #1e2040); }
    .flow-node.agent { border-color: var(--purple); }
    .flow-node.skill { border-color: var(--blue); }
    .flow-node.script { border-color: var(--cyan); }
    .flow-node.file { border-color: var(--orange); }
    .flow-node.api { border-color: var(--amber); }
    .flow-node.delivery { border-color: var(--green); }
    .flow-node.platform { border-color: var(--green); }
    .flow-node.noop { border-color: var(--muted); opacity: 0.5; }
    .flow-node.process { border-color: var(--cyan); }
    .flow-arrow {
      color: var(--muted);
      font-size: 16px;
      padding: 2px 0;
      text-align: center;
    }
    .flow-arrow .label { font-size: 10px; display: block; }

    .flow-branch {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: 4px;
    }
    .flow-branch-col {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 10px;
      margin-top: 16px;
    }
    .detail-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
    }
    .detail-card .dt { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 4px; }
    .detail-card .dd { font-size: 13px; word-break: break-word; }
    .detail-card .dd.code { font-family: 'SF Mono', monospace; font-size: 12px; }
    .detail-card .dd.ok { color: var(--green); }
    .detail-card .dd.warn { color: var(--amber); }
    .detail-card .dd.err { color: var(--red); }

    .skills-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .skill-chip {
      font-size: 11px;
      padding: 3px 10px;
      border-radius: 4px;
      background: rgba(99,102,241,0.1);
      border: 1px solid rgba(99,102,241,0.25);
      color: var(--primary);
    }

    .empty-state {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 200px;
      color: var(--muted);
      font-size: 14px;
    }

    .back-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      color: var(--text);
      font-size: 12px;
      cursor: pointer;
      margin-bottom: 16px;
    }
    .back-btn:hover { border-color: var(--primary); }

    .error-state {
      padding: 20px;
      text-align: center;
      color: var(--red);
      font-size: 13px;
    }
  `;
  document.head.appendChild(styles);

  // ══════════════════════════════════════════════════════════
  //  HELPERS
  // ══════════════════════════════════════════════════════════
  function h(tag, attrs) {
    for (
      var _len = arguments.length, children = new Array(_len > 2 ? _len - 2 : 0), _key = 2;
      _key < _len;
      _key++
    ) {
      children[_key - 2] = arguments[_key];
    }
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k.startsWith('on') && typeof attrs[k] === 'function') {
          el.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        } else if (k === 'className') {
          el.className = attrs[k];
        } else if (k === 'style' && typeof attrs[k] === 'object') {
          Object.assign(el.style, attrs[k]);
        } else {
          el.setAttribute(k, attrs[k]);
        }
      });
    }
    function append(child) {
      if (child == null || child === false) return;
      if (typeof child === 'string' || typeof child === 'number') {
        el.appendChild(document.createTextNode(String(child)));
      } else if (Array.isArray(child)) {
        child.forEach(append);
      } else if (child instanceof Node) {
        el.appendChild(child);
      }
    }
    children.forEach(append);
    return el;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ══════════════════════════════════════════════════════════
  //  JOB ANALYSIS
  // ══════════════════════════════════════════════════════════
  function analyzeJob(job) {
    var info = {
      id: job.id,
      name: job.name || 'Unnamed job',
      schedule:
        job.schedule_display ||
        (job.schedule && job.schedule.display) ||
        (job.schedule && job.schedule.expr) ||
        '?',
      no_agent: !!job.no_agent,
      script: job.script || null,
      skills: Array.isArray(job.skills) ? job.skills : [],
      provider: job.provider || null,
      model: job.model || null,
      deliver: job.deliver || 'local',
      last_run: job.last_run_at || null,
      last_status: job.last_status || null,
      last_error: job.last_error || null,
      next_run: job.next_run_at || null,
      enabled: job.enabled !== false,
    };
    return info;
  }

  function scheduleSummary(expr) {
    if (!expr) return '?';
    if (expr.startsWith('every')) return expr;
    var parts = expr.split(/\s+/);
    if (parts.length === 5) {
      var min = parts[0],
        hr = parts[1],
        dom = parts[2],
        mon = parts[3],
        dow = parts[4];
      if (dom === '*' && mon === '*' && dow === '*')
        return 'Daily at ' + String(hr).padStart(2, '0') + ':' + String(min).padStart(2, '0');
      if (dom === '*' && mon === '*' && dow !== '*') return 'Weekly';
      if (dom !== '*' && mon === '*' && dow === '*') return 'Monthly (day ' + dom + ')';
    }
    return expr;
  }

  function platformIcon(deliver) {
    if (!deliver || deliver === 'local') return '💾';
    if (deliver.includes('whatsapp')) return '💬';
    if (deliver.includes('telegram')) return '✈️';
    if (deliver.includes('email')) return '📧';
    if (deliver.includes('discord')) return '🎮';
    if (deliver.includes('slack')) return '💼';
    return '📤';
  }

  // ══════════════════════════════════════════════════════════
  //  PROFILE RESOLUTION: custom + fallback to examples
  // ══════════════════════════════════════════════════════════
  function resolveProfile(jobId) {
    // User's custom profiles take priority
    if (CUSTOM_PROFILES[jobId]) return CUSTOM_PROFILES[jobId];
    // Fall back to example profiles (for illustration)
    if (EXAMPLE_PROFILES[jobId]) return EXAMPLE_PROFILES[jobId];
    return null;
  }

  // ══════════════════════════════════════════════════════════
  //  RENDER: job list
  // ══════════════════════════════════════════════════════════
  function renderJobList(container, jobs) {
    container.innerHTML = '';
    container.appendChild(
      h(
        'h1',
        null,
        '🔄',
        'Cron Flow Visualization — select a job',
        h('small', null, jobs.length + ' jobs'),
      ),
    );

    var list = h('div', { className: 'job-list' });

    // Sort: active first, then by name
    var sorted = jobs.slice().sort(function (a, b) {
      var aActive = a.enabled !== false ? 0 : 1;
      var bActive = b.enabled !== false ? 0 : 1;
      if (aActive !== bActive) return aActive - bActive;
      return (a.name || '').localeCompare(b.name || '');
    });

    sorted.forEach(function (job) {
      var info = analyzeJob(job);
      var hasProfile = !!resolveProfile(job.id);
      var iconType = info.no_agent ? 'script' : hasProfile ? 'hybrid' : 'agent';
      var statusDot = info.enabled ? '' : '⏸️';
      var statusBadge = info.last_status === 'ok' ? '✅' : info.last_status === 'error' ? '❌' : '';
      var scheduleShort = scheduleSummary(info.schedule);

      var item = h('div', {
        className: 'job-item',
        onclick: function () {
          showJobDetail(container, jobs, job);
        },
      });
      item.appendChild(
        h(
          'div',
          { className: 'job-icon ' + iconType },
          info.no_agent ? '📜' : hasProfile ? '🔬' : '🤖',
        ),
      );
      var infoDiv = h('div', { className: 'job-info' });
      infoDiv.appendChild(
        h(
          'div',
          { className: 'job-name' },
          statusDot,
          ' ',
          info.name,
          ' ',
          h('span', null, statusBadge),
        ),
      );
      var meta = h('div', { className: 'job-meta' });
      meta.appendChild(h('span', { className: 'chip' }, scheduleShort));
      if (hasProfile) meta.appendChild(h('span', { className: 'chip' }, '🔬 detailed'));
      if (info.no_agent && info.script)
        meta.appendChild(h('span', { className: 'chip' }, '📜 ' + info.script));
      if (info.provider) meta.appendChild(h('span', { className: 'chip' }, info.provider));
      if (info.skills.length)
        meta.appendChild(h('span', { className: 'chip' }, info.skills.length + ' skills'));
      meta.appendChild(
        h(
          'span',
          { className: 'chip' },
          platformIcon(info.deliver) + ' ' + (info.deliver ? info.deliver.split(':')[0] : 'local'),
        ),
      );
      infoDiv.appendChild(meta);
      item.appendChild(infoDiv);
      item.appendChild(h('span', { className: 'job-arrow' }, '→'));
      list.appendChild(item);
    });

    container.appendChild(list);
  }

  // ══════════════════════════════════════════════════════════
  //  RENDER: agent flow with profile
  // ══════════════════════════════════════════════════════════
  function renderAgentFlowWithProfile(flow, info, profile) {
    flow.appendChild(flowNode('cron', '⏰', 'Cron Trigger', info.schedule));
    flow.appendChild(arrow('triggers'));
    flow.appendChild(
      flowNode(
        'agent',
        '🤖',
        'AI Agent',
        (info.provider || 'default') + ' · ' + (info.model || '?'),
      ),
    );
    flow.appendChild(arrow('executes process'));

    if (profile.process) {
      profile.process.forEach(function (step, i) {
        flow.appendChild(flowNode('process', '⚙️', step.label, step.detail));
        if (i < profile.process.length - 1) flow.appendChild(arrow('↓'));
      });
    }

    flow.appendChild(arrow('output'));
    flow.appendChild(flowNode('platform', platformIcon(info.deliver), 'Platform', info.deliver));

    if (info.skills.length) {
      var skillNote = h('div', {
        className: 'skills-list',
        style: { marginTop: '8px', justifyContent: 'center' },
      });
      info.skills.forEach(function (s) {
        skillNote.appendChild(h('span', { className: 'skill-chip' }, s));
      });
      flow.appendChild(skillNote);
    }
  }

  // ══════════════════════════════════════════════════════════
  //  RENDER: job detail / flow diagram
  // ══════════════════════════════════════════════════════════
  function showJobDetail(container, allJobs, job) {
    container.innerHTML = '';

    var info = analyzeJob(job);
    var profile = resolveProfile(job.id);

    // Back button
    var backBtn = h(
      'button',
      {
        className: 'back-btn',
        onclick: function () {
          renderJobList(container, allJobs);
        },
      },
      '← Back to list',
    );

    // Header
    var icon = info.no_agent ? '📜' : '🤖';
    var typeLabel = info.no_agent ? 'no_agent script' : profile ? 'AI agent + detail' : 'AI agent';
    var header = h('div', { style: { marginBottom: '16px' } });
    header.appendChild(backBtn);
    header.appendChild(
      h(
        'h1',
        null,
        icon,
        ' ',
        info.name,
        h('small', null, typeLabel + ' · ' + String(info.id).substring(0, 8)),
      ),
    );

    var statusColor =
      info.last_status === 'ok' ? 'ok' : info.last_status === 'error' ? 'err' : 'warn';
    var statusText = info.last_status || 'never run';

    // Info cards
    var detailGrid = h('div', { className: 'detail-grid' });
    detailGrid.appendChild(detailCard('⏰ Schedule', scheduleSummary(info.schedule), true));
    detailGrid.appendChild(detailCard('📊 Status', statusText, false, statusColor));
    detailGrid.appendChild(detailCard('📤 Delivery', info.deliver, true));
    if (info.last_run)
      detailGrid.appendChild(
        detailCard('🕐 Last run', new Date(info.last_run).toLocaleString(), false),
      );
    if (info.next_run)
      detailGrid.appendChild(
        detailCard('⏳ Next run', new Date(info.next_run).toLocaleString(), false),
      );
    if (info.last_error)
      detailGrid.appendChild(detailCard('⚠️ Error', info.last_error, false, 'err'));
    if (info.provider) detailGrid.appendChild(detailCard('⚙️ Provider', info.provider, false));
    if (info.model) detailGrid.appendChild(detailCard('🧠 Model', info.model, false));
    if (info.script) detailGrid.appendChild(detailCard('📜 Script path', info.script, true));
    header.appendChild(detailGrid);

    // Skills
    if (info.skills.length) {
      var skillsSec = h('div', { style: { marginTop: '12px' } });
      skillsSec.appendChild(
        h(
          'div',
          { style: { fontSize: '12px', fontWeight: 600, marginBottom: '6px' } },
          '🧩 Skills',
        ),
      );
      var skillChips = h('div', { className: 'skills-list' });
      info.skills.forEach(function (s) {
        skillChips.appendChild(h('span', { className: 'skill-chip' }, s));
      });
      skillsSec.appendChild(skillChips);
      header.appendChild(skillsSec);
    }

    container.appendChild(header);

    // ── Flow diagram ──
    container.appendChild(h('div', { className: 'flow-section' }, h('h2', null, '📊 Data Flow')));

    var flow = h('div', { className: 'flow-diagram' });

    if (info.no_agent && info.script) {
      // no_agent: cron → script → output → delivery
      flow.appendChild(flowNode('cron', '⏰', 'Cron Trigger', info.schedule));
      flow.appendChild(arrow('triggers'));
      flow.appendChild(flowNode('script', '📜', 'Script', info.script));
      flow.appendChild(arrow('runs (no_agent)'));

      if (profile) {
        flow.appendChild(arrow('↙ branches ↘'));
        var branch = h('div', { className: 'flow-branch' });

        // Data sources
        var readCol = h('div', { className: 'flow-branch-col' });
        readCol.appendChild(flowNode('file', '📂', 'State / Files', 'reads and writes'));
        if (profile.connections) {
          profile.connections.forEach(function (c) {
            if (c.type === 'api' || c.type === 'file') {
              readCol.appendChild(arrow(c.direction === 'write' ? 'writes' : 'reads'));
              readCol.appendChild(
                flowNode(c.type, c.type === 'api' ? '🌐' : '📄', c.label, c.detail),
              );
            }
          });
        }
        branch.appendChild(readCol);

        // Process + output
        var procCol = h('div', { className: 'flow-branch-col' });
        if (profile.process) {
          profile.process.forEach(function (p) {
            procCol.appendChild(arrow('→'));
            procCol.appendChild(flowNode('api', '⚙️', p.label, p.detail));
          });
        }
        procCol.appendChild(arrow('creates'));
        procCol.appendChild(flowNode('file', '📄', 'Output', 'local file / stdout'));
        branch.appendChild(procCol);

        flow.appendChild(branch);
      } else {
        flow.appendChild(arrow('stdout'));
        flow.appendChild(flowNode('file', '📄', 'Stdout output', 'text notification'));
        flow.appendChild(arrow('delivers'));
        flow.appendChild(
          flowNode('platform', platformIcon(info.deliver), 'Platform', info.deliver),
        );
      }
    } else if (profile) {
      // Agent job with known profile — expanded flow
      renderAgentFlowWithProfile(flow, info, profile);
    } else if (info.skills.length) {
      // Agent job with skills but no profile: cron → agent → skills → output
      flow.appendChild(flowNode('cron', '⏰', 'Cron Trigger', info.schedule));
      flow.appendChild(arrow('triggers'));
      flow.appendChild(
        flowNode(
          'agent',
          '🤖',
          'AI Agent',
          (info.provider || 'default') + ' · ' + (info.model || '?'),
        ),
      );
      flow.appendChild(arrow('uses skills'));

      if (info.skills.length <= 5) {
        info.skills.forEach(function (s, i) {
          flow.appendChild(flowNode('skill', '🧩', s, 'skill'));
          if (i < info.skills.length - 1) flow.appendChild(arrow(''));
        });
      } else {
        flow.appendChild(
          flowNode('skill', '🧩', info.skills.length + ' skills', info.skills.join(', ')),
        );
      }

      flow.appendChild(arrow('output'));
      flow.appendChild(flowNode('platform', platformIcon(info.deliver), 'Platform', info.deliver));
    } else {
      // Generic agent job
      flow.appendChild(flowNode('cron', '⏰', 'Cron Trigger', info.schedule));
      flow.appendChild(arrow('triggers'));
      flow.appendChild(
        flowNode(
          'agent',
          '🤖',
          'AI Agent',
          (info.provider || 'default') + (info.model ? ' · ' + info.model : ''),
        ),
      );
      flow.appendChild(arrow('output'));
      flow.appendChild(flowNode('platform', platformIcon(info.deliver), 'Platform', info.deliver));
    }

    container.appendChild(flow);

    // ── Connection details ──
    if (profile && profile.connections) {
      container.appendChild(
        h('div', { className: 'flow-section' }, h('h2', null, '🔗 Known Connections')),
      );

      var connGrid = h('div', { className: 'detail-grid' });
      profile.connections.forEach(function (c) {
        var card = h('div', { className: 'detail-card' });
        card.appendChild(
          h(
            'div',
            { className: 'dt' },
            c.type.toUpperCase() + (c.direction ? ' · ' + c.direction : ''),
          ),
        );
        card.appendChild(h('div', { className: 'dd' }, c.label));
        card.appendChild(
          h(
            'div',
            { className: 'dd code', style: { marginTop: '4px', color: 'var(--muted)' } },
            c.detail,
          ),
        );
        if (c.auth)
          card.appendChild(
            h(
              'div',
              {
                className: 'dd code',
                style: { marginTop: '2px', fontSize: '11px', color: 'var(--amber)' },
              },
              '🔑 ' + c.auth,
            ),
          );
        if (c.url)
          card.appendChild(
            h(
              'div',
              {
                className: 'dd code',
                style: { marginTop: '2px', fontSize: '10px', color: 'var(--muted)' },
              },
              c.url,
            ),
          );
        connGrid.appendChild(card);
      });
      container.appendChild(connGrid);

      // Process steps
      if (profile.process) {
        var procBox = h('div', {
          style: {
            marginTop: '16px',
            padding: '14px',
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            fontSize: '12px',
          },
        });
        procBox.appendChild(
          h(
            'div',
            { style: { fontWeight: 600, marginBottom: '8px', color: 'var(--muted)' } },
            '📋 Process Steps',
          ),
        );
        var stepList = h('div', {
          style: { display: 'flex', flexDirection: 'column', gap: '4px' },
        });
        profile.process.forEach(function (step) {
          stepList.appendChild(
            h(
              'div',
              { style: { display: 'flex', gap: '6px', alignItems: 'flex-start' } },
              h('span', { style: { color: 'var(--cyan)', flexShrink: 0 } }, '▸'),
              h('span', null, h('strong', null, step.label), ': ', step.detail),
            ),
          );
        });
        procBox.appendChild(stepList);
        container.appendChild(procBox);
      }

      // Legend
      var legend = h('div', {
        style: {
          marginTop: '16px',
          padding: '12px',
          background: 'var(--card)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          fontSize: '12px',
        },
      });
      legend.appendChild(
        h(
          'div',
          { style: { fontWeight: 600, marginBottom: '8px', color: 'var(--muted)' } },
          'Legend',
        ),
      );
      var legendItems = h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '10px' } });
      [
        ['#6366f1', 'Cron trigger'],
        ['#a855f7', 'AI Agent'],
        ['#3b82f6', 'Skill'],
        ['#06b6d4', 'Script / Process step'],
        ['#f59e0b', 'External API'],
        ['#f97316', 'File / Storage'],
        ['#22c55e', 'Delivery'],
      ].forEach(function (pair) {
        legendItems.appendChild(
          h(
            'div',
            { style: { display: 'flex', alignItems: 'center', gap: '4px' } },
            h('span', {
              style: {
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: pair[0],
                display: 'inline-block',
              },
            }),
            pair[1],
          ),
        );
      });
      legend.appendChild(legendItems);
      container.appendChild(legend);
    }

    // ── No-profile hint ──
    if (!profile && !info.no_agent && info.skills.length) {
      var hintBox = h('div', {
        style: {
          marginTop: '16px',
          padding: '14px',
          background: 'var(--card)',
          border: '1px solid var(--amber)',
          borderRadius: '8px',
          fontSize: '12px',
          color: 'var(--amber)',
        },
      });
      hintBox.innerHTML =
        '<strong>💡 No detailed profile for this job.</strong><br>' +
        'To add one, edit <code>CUSTOM_PROFILES</code> in <code>dashboard/dist/index.js</code> — ' +
        'add an entry with the job ID <code>' +
        esc(info.id) +
        '</code>, a <code>connections</code> array, and a <code>process</code> array. ' +
        'See the <code>EXAMPLE_PROFILES</code> section for the format.';
      container.appendChild(hintBox);
    }
  }

  function detailCard(label, value, isCode, colorClass) {
    var card = h('div', { className: 'detail-card' });
    card.appendChild(h('div', { className: 'dt' }, label));
    var ddClass = 'dd' + (isCode ? ' code' : '') + (colorClass ? ' ' + colorClass : '');
    card.appendChild(h('div', { className: ddClass }, value || '—'));
    return card;
  }

  function flowNode(type, icon, title, sub) {
    return h(
      'div',
      { className: 'flow-node ' + type },
      h('div', { className: 'icon' }, icon),
      h('div', { className: 'title' }, title),
      sub ? h('div', { className: 'sub' }, sub) : null,
    );
  }

  function arrow(label) {
    return h(
      'div',
      { className: 'flow-arrow' },
      '↓',
      label ? h('span', { className: 'label' }, label) : null,
    );
  }

  // ══════════════════════════════════════════════════════════
  //  INIT
  // ══════════════════════════════════════════════════════════
  function init() {
    var root = document.getElementById('pluginPageContainer') || document.body;
    root.innerHTML = '<div class="empty-state">⏳ Loading cron jobs...</div>';

    fetch('/api/taskflow/jobs', { method: 'GET', credentials: 'omit' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.jobs || !data.jobs.length) {
          root.innerHTML =
            '<div class="error-state">⚠️ No cron jobs found. Make sure the backend endpoint is set up (see BACKEND-SETUP.md).</div>';
          return;
        }
        renderJobList(root, data.jobs);
      })
      .catch(function (err) {
        root.innerHTML =
          '<div class="error-state">⚠️ Failed to load cron jobs: ' +
          esc(err.message) +
          '<br><br>Make sure the Hermes WebUI is running and the backend endpoint is configured (see BACKEND-SETUP.md).</div>';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
