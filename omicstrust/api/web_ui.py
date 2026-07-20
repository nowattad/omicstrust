from __future__ import annotations


def render_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OmicsTrust Private Audit Console</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #171b22;
      --muted: #626b78;
      --line: #dfe3e8;
      --panel: #ffffff;
      --bg: #f5f6f7;
      --accent: #0f6b61;
      --accent-strong: #0b514a;
      --navy: #17324d;
      --bad: #a23232;
      --good: #14724f;
      --warn: #946200;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }
    header { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 14px 22px; background: rgba(255,255,255,.97); border-bottom: 1px solid var(--line); }
    .brand { display: flex; align-items: center; gap: 11px; min-width: 210px; }
    .brand-mark { width: 34px; height: 34px; display: grid; place-items: center; background: var(--navy); color: #fff; border-radius: 7px; font-size: 12px; font-weight: 800; }
    .brand-line { display: flex; align-items: center; gap: 7px; margin-top: 2px; }
    .status-chip { display: inline-flex; align-items: center; gap: 6px; min-height: 26px; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; background: #fff; color: var(--muted); font-size: 11px; font-weight: 700; white-space: nowrap; }
    .status-chip::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--warn); }
    .status-chip.ready::before { background: var(--good); }
    .ruo-chip { border-color: #e6c56f; color: #725000; background: #fff9e8; }
    .ruo-chip::before { background: var(--warn); }
    .header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .token-input { width: min(260px, 44vw); }
    h1 { font-size: 20px; margin: 0; letter-spacing: 0; }
    main { display: grid; grid-template-columns: minmax(320px, 420px) minmax(0, 1fr); gap: 0; min-height: calc(100vh - 64px); max-width: 1560px; margin: 0 auto; background: var(--panel); border-left: 1px solid var(--line); border-right: 1px solid var(--line); }
    main > section:first-child { border-right: 1px solid var(--line); }
    section { background: var(--panel); border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: 18px; }
    h2 { margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }
    label { display: block; font-size: 12px; font-weight: 700; color: #344054; margin: 12px 0 5px; }
    input, select, textarea {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    textarea { min-height: 170px; resize: vertical; line-height: 1.45; }
    .tabs { display: inline-flex; gap: 2px; flex-wrap: wrap; padding: 3px; background: #eef1f3; border-radius: 8px; }
    .tabs button { border-color: transparent; background: transparent; }
    .tab-button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .view.hidden { display: none; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .buttons { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    button, .link-button {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 7px 11px;
      font-weight: 720;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .muted { color: var(--muted); font-size: 13px; }
    .notice { border: 1px solid var(--line); border-radius: 8px; background: #fbfcfe; padding: 10px; margin-top: 12px; color: var(--muted); font-size: 13px; white-space: pre-wrap; overflow-wrap: anywhere; }
    .hint-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
    .hint { border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; background: #fff; color: #344054; font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfe; }
    .metric span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0; }
    .metric strong { display: block; margin-top: 5px; font-size: 17px; overflow-wrap: anywhere; }
    .jobs-list { display: grid; gap: 8px; }
    .job-card {
      display: grid;
      grid-template-columns: minmax(130px, 1.2fr) 92px 88px 70px minmax(160px, 1.4fr) minmax(170px, 1fr);
      gap: 10px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fff;
      cursor: pointer;
    }
    .job-card:hover { border-color: var(--accent); }
    .job-label { display: block; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0; margin-bottom: 3px; }
    .job-value { display: block; font-size: 12px; font-weight: 650; overflow-wrap: anywhere; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }
    th { color: #344054; background: #eef3f7; }
    .status-completed { color: var(--good); font-weight: 800; }
    .status-failed { color: var(--bad); font-weight: 800; }
    .status-running, .status-queued { color: var(--warn); font-weight: 800; }
    .progress-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
    .progress-list li { border-bottom: 1px solid var(--line); padding: 7px 0; color: var(--muted); font-size: 13px; }
    .copilot-answer { font-size: 15px; line-height: 1.45; margin: 0 0 12px; }
    .candidate-card { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfe; }
    .candidate-card h3 { margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }
    .badges { display: flex; flex-wrap: wrap; gap: 6px; margin: 7px 0; }
    .badge { border: 1px solid var(--line); border-radius: 999px; padding: 3px 7px; background: #fff; color: #344054; font-size: 11px; font-weight: 760; }
    .candidate-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-top: 8px; }
    .candidate-field span { display: block; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0; }
    .ai-control { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; margin-top: 14px; padding: 11px; border: 1px solid #b9d9d4; background: #f2faf8; border-radius: 7px; }
    .ai-control input { width: 18px; min-height: 18px; margin-top: 2px; accent-color: var(--accent); }
    .ai-control label { margin: 0; font-size: 13px; }
    .ai-control small { display: block; margin-top: 3px; color: var(--muted); line-height: 1.35; }
    .evidence-band { background: #f8fafb; border-left: 3px solid var(--navy); }
    .claim-ok { border-left: 3px solid var(--good); }
    .claim-limit { border-left: 3px solid var(--warn); }
    .pc11-view { grid-template-columns: minmax(320px, 430px) minmax(0, 1fr); }
    .pc11-report { min-height: 760px; border-radius: 0; border-width: 0 0 0 1px; }
    .candidate-field strong { display: block; font-size: 12px; overflow-wrap: anywhere; }
    iframe { width: 100%; min-height: 620px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .pc11-view { grid-template-columns: 1fr; }
      main > section:first-child { border-right: 0; }
      .job-card { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      header { align-items: stretch; flex-direction: column; gap: 10px; }
      .brand { min-width: 0; }
      .header-actions { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto auto auto; justify-content: stretch; }
      .header-actions > * { min-width: 0; }
      .tabs { grid-column: 1 / -1; width: 100%; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .tabs button { min-width: 0; justify-content: center; white-space: normal; }
      .token-input { width: 100%; }
    }
    @media (max-width: 520px) {
      header { padding: 12px; }
      .header-actions { grid-template-columns: 1fr 1fr; }
      .tabs, #aiHeaderStatus, .token-input { grid-column: 1 / -1; }
      #aiHeaderStatus { justify-content: center; }
      .row { grid-template-columns: 1fr; }
      .job-card { grid-template-columns: 1fr; }
      section { padding: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-mark">OT</div>
      <div>
        <h1>OmicsTrust</h1>
        <div class="brand-line"><span class="muted">Evidence audit console</span><span class="status-chip ruo-chip">RUO</span></div>
      </div>
    </div>
    <div class="header-actions">
      <div class="tabs">
        <button class="tab-button active" data-view="auditView">Audit</button>
        <button class="tab-button" data-view="copilotView">Evidence Copilot</button>
        <button class="tab-button" data-view="pc11View">PC11 Evidence</button>
      </div>
      <span id="aiHeaderStatus" class="status-chip">GPT-5.6</span>
      <input id="apiToken" class="token-input" type="password" placeholder="Optional API token">
      <button id="saveToken">Save Token</button>
      <button id="refreshJobs">Refresh</button>
    </div>
  </header>
  <main id="auditView" class="view">
    <section>
      <h2>Run Audit</h2>
      <form id="uploadForm">
        <label for="file">Upload .h5ad or .csv</label>
        <input id="file" name="file" type="file" accept=".h5ad,.csv,.tsv,.txt">
        <div class="row">
          <div>
            <label for="batch_key">Batch key</label>
            <input id="batch_key" name="batch_key" placeholder="batch">
          </div>
          <div>
            <label for="donor_key">Donor key</label>
            <input id="donor_key" name="donor_key" placeholder="donor">
          </div>
        </div>
        <label for="label_key">Biological label key</label>
        <input id="label_key" name="label_key" placeholder="condition, disease, cell_type">
        <label for="config_path">Config path</label>
        <input id="config_path" name="config_path" placeholder="configs/singlecell_audit.yaml">
        <div class="buttons">
          <button class="primary" type="submit">Run Uploaded Audit</button>
        </div>
      </form>

      <h2 style="margin-top: 22px;">Audit Existing Local Path</h2>
      <form id="pathForm">
        <label for="data_path">Data path</label>
        <input id="data_path" name="data_path" placeholder="/path/to/data.h5ad">
        <div class="buttons">
          <button class="primary" type="submit">Run Path Audit</button>
          <button id="inspectPath" type="button">Inspect</button>
        </div>
      </form>
      <pre id="inspectOutput" class="muted"></pre>
      <div id="metadataHints" class="hint-list"></div>
      <div id="statusLine" class="notice">Ready. Run a local audit or inspect a dataset path.</div>
    </section>

    <div>
      <section>
        <h2>Current Result</h2>
        <div id="summary" class="grid"></div>
        <div id="links" class="buttons"></div>
      </section>

      <section style="margin-top: 18px;">
        <h2>Audit History</h2>
        <div id="jobs" class="jobs-list"></div>
      </section>

      <section style="margin-top: 18px;">
        <h2>Case Studies</h2>
        <div id="caseStudies" class="jobs-list"></div>
      </section>

      <section style="margin-top: 18px;">
        <h2>Report Preview</h2>
        <iframe id="reportFrame" title="OmicsTrust report preview"></iframe>
      </section>
    </div>
  </main>

  <main id="copilotView" class="view hidden">
    <section>
      <h2>Ask OmicsTrust</h2>
      <form id="copilotForm">
        <label for="copilot_request">Describe your biomedical discovery question</label>
        <textarea id="copilot_request" name="user_request" placeholder="Example: Audit whether this single-cell dataset has a batch-dominated signal before biological interpretation."></textarea>
        <label for="copilot_workflow">Workflow</label>
        <select id="copilot_workflow" name="workflow">
          <option value="">Auto planner</option>
          <option value="public_dataset_search">Public dataset search</option>
          <option value="dataset_inspection">Dataset inspection</option>
          <option value="singlecell_audit">Single-cell audit</option>
          <option value="treatment_response_audit">Treatment-response audit</option>
          <option value="de_novo_treatment_response_discovery">De novo treatment-response discovery</option>
          <option value="locked_validation">Locked-axis validation</option>
          <option value="case_study_demo">Case-study demo</option>
        </select>
        <label for="copilot_data_mode">Data mode</label>
        <select id="copilot_data_mode" name="data_mode">
          <option value="uploaded">I have my own data</option>
          <option value="local_path">Use existing local path</option>
          <option value="public_search">Search public datasets</option>
        </select>
        <label for="copilot_file">Optional upload</label>
        <input id="copilot_file" name="data_file" type="file" accept=".h5ad,.csv,.tsv,.txt">
        <label for="copilot_metadata_file">Optional metadata.csv</label>
        <input id="copilot_metadata_file" name="metadata_file" type="file" accept=".csv,.tsv,.txt">
        <label for="copilot_data_path">Optional local path</label>
        <input id="copilot_data_path" name="data_path" placeholder="/path/to/data.h5ad">
        <div class="row">
          <div>
            <label for="copilot_batch_key">Batch key</label>
            <input id="copilot_batch_key" name="batch_key" placeholder="batch">
          </div>
          <div>
            <label for="copilot_donor_key">Donor key</label>
            <input id="copilot_donor_key" name="donor_key" placeholder="patient_id">
          </div>
        </div>
        <label for="copilot_label_key">Label / outcome key</label>
        <input id="copilot_label_key" name="label_key" placeholder="response, mortality, disease">
        <div class="row">
          <div>
            <label for="copilot_treatment_key">Treatment key</label>
            <input id="copilot_treatment_key" name="treatment_key" placeholder="treatment, therapy, arm">
          </div>
          <div>
            <label for="copilot_outcome_key">Outcome key</label>
            <input id="copilot_outcome_key" name="outcome_key" placeholder="response, death_28">
          </div>
        </div>
        <label for="copilot_dataset_adapter">Dataset adapter</label>
        <input id="copilot_dataset_adapter" name="dataset_adapter" placeholder="vanish_default_mapping">
        <label for="copilot_config_path">Config path</label>
        <input id="copilot_config_path" name="config_path" placeholder="configs/singlecell_audit.yaml">
        <div class="ai-control">
          <input id="copilot_use_ai" name="use_ai" type="checkbox" value="true" checked>
          <label for="copilot_use_ai">GPT-5.6 evidence interpretation
            <small>Only the question, supplied field names, and deterministic summary are sent. Expression matrices and patient rows stay local.</small>
          </label>
          <input type="hidden" name="ai_model" value="gpt-5.6">
        </div>
        <div class="buttons">
          <button class="primary" type="submit">Run Evidence Copilot</button>
        </div>
      </form>
      <div id="copilotStatus" class="notice">Ready.</div>
    </section>

    <div>
      <section>
        <h2>Copilot Result</h2>
        <p id="copilotAnswer" class="copilot-answer muted">No copilot result yet.</p>
        <div id="copilotSummary" class="grid"></div>
        <div id="copilotLinks" class="buttons"></div>
      </section>

      <section style="margin-top: 18px;">
        <h2>Job Progress</h2>
        <ul id="copilotProgress" class="progress-list"></ul>
      </section>

      <section style="margin-top: 18px;">
        <h2>Claim Boundary</h2>
        <table>
          <tbody id="copilotClaims"></tbody>
        </table>
      </section>

      <section id="aiInterpretationSection" class="evidence-band" style="display:none;">
        <h2>GPT-5.6 Evidence Interpretation</h2>
        <div id="aiInterpretation" class="notice"></div>
      </section>
    </div>
  </main>

  <main id="pc11View" class="view hidden pc11-view">
    <section>
      <h2>VANISH PC11 / VasoGate</h2>
      <p class="copilot-answer">A retrospective transcriptomic treatment-response hypothesis discovered by OmicsTrust in VANISH.</p>
      <div class="grid">
        <div class="metric"><span>Patients</span><strong>116</strong></div>
        <div class="metric"><span>Features</span><strong>28,220</strong></div>
        <div class="metric"><span>Axes Screened</span><strong>25</strong></div>
        <div class="metric"><span>Top Axis</span><strong>PC11</strong></div>
        <div class="metric"><span>OR / 1 SD</span><strong>0.1688</strong></div>
        <div class="metric"><span>BH FDR</span><strong>0.03145</strong></div>
        <div class="metric"><span>Permutation p</span><strong>0.003996</strong></div>
        <div class="metric"><span>Bootstrap Direction</span><strong>99.9%</strong></div>
      </div>
      <div class="notice claim-ok"><strong>Supported</strong><br>A stable internal treatment-by-axis interaction hypothesis within the analyzed VANISH cohort.</div>
      <div class="notice claim-limit"><strong>Not supported</strong><br>Clinical treatment selection, biomarker qualification, causal mechanism, or external validation.</div>
      <div class="buttons">
        <a class="link-button" href="/api/case-studies/vanish_vasogate_pc11/report.pdf" target="_blank">Open Report</a>
        <a class="link-button" href="/api/case-studies/vanish_vasogate_pc11/discovery-summary.json" target="_blank">Evidence JSON</a>
      </div>
      <div class="notice">Research Use Only. Independent-cohort validation is required.</div>
    </section>
    <div>
      <section>
        <h2>Preserved Research Report</h2>
        <iframe class="pc11-report" src="/api/case-studies/vanish_vasogate_pc11/report.pdf" title="VANISH PC11 preserved research report"></iframe>
      </section>
    </div>
  </main>
  <script>
    const jobsBody = document.getElementById('jobs');
    const summary = document.getElementById('summary');
    const links = document.getElementById('links');
    const reportFrame = document.getElementById('reportFrame');
    const statusLine = document.getElementById('statusLine');
    const metadataHints = document.getElementById('metadataHints');
    const caseStudies = document.getElementById('caseStudies');
    const apiTokenInput = document.getElementById('apiToken');
    const copilotStatus = document.getElementById('copilotStatus');
    const copilotAnswer = document.getElementById('copilotAnswer');
    const copilotSummary = document.getElementById('copilotSummary');
    const copilotProgress = document.getElementById('copilotProgress');
    const copilotLinks = document.getElementById('copilotLinks');
    const copilotClaims = document.getElementById('copilotClaims');
    const aiHeaderStatus = document.getElementById('aiHeaderStatus');
    const aiInterpretationSection = document.getElementById('aiInterpretationSection');
    const aiInterpretation = document.getElementById('aiInterpretation');
    let selectedJobId = null;

    function valueOrDash(value) { return value === null || value === undefined || value === '' ? 'not available' : value; }
    function escapeHtml(value) {
      return String(valueOrDash(value)).replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      })[char]);
    }
    function safeExternalUrl(value) {
      try {
        const parsed = new URL(String(value));
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '#';
      } catch (_) {
        return '#';
      }
    }
    function metric(label, value) { return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`; }
    function apiToken() { return localStorage.getItem('omicstrust_token') || ''; }
    function authHeaders(json=false) {
      const headers = json ? {'Content-Type': 'application/json'} : {};
      const token = apiToken();
      if (token) headers['X-OmicsTrust-Token'] = token;
      return headers;
    }
    async function apiFetch(url, options={}) {
      const merged = Object.assign({}, options);
      merged.headers = Object.assign({}, options.headers || {}, authHeaders(false));
      const res = await fetch(url, merged);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status} ${text}`);
      }
      return res;
    }
    function setStatus(text) { statusLine.textContent = text; }
    function setCopilotStatus(text) { copilotStatus.textContent = text; }

    async function loadHealth() {
      try {
        const res = await fetch('/health');
        const health = await res.json();
        const ai = health.evidence_copilot || {};
        aiHeaderStatus.textContent = `${ai.default_model || 'GPT-5.6'} ${ai.openai_configured ? 'ready' : 'optional'}`;
        aiHeaderStatus.classList.toggle('ready', !!ai.openai_configured);
      } catch (_) {
        aiHeaderStatus.textContent = 'GPT-5.6 status unavailable';
      }
    }

    function switchView(viewId) {
      document.querySelectorAll('.view').forEach(view => view.classList.add('hidden'));
      document.getElementById(viewId).classList.remove('hidden');
      document.querySelectorAll('.tab-button').forEach(button => button.classList.toggle('active', button.dataset.view === viewId));
    }

    async function createPathJob(event) {
      event.preventDefault();
      setStatus('Running path audit...');
      const form = new FormData(event.target);
      const payload = Object.fromEntries(form.entries());
      payload.batch_key = document.getElementById('batch_key').value;
      payload.donor_key = document.getElementById('donor_key').value;
      payload.label_key = document.getElementById('label_key').value;
      payload.config_path = document.getElementById('config_path').value;
      payload.background = false;
      try {
        const res = await apiFetch('/api/audits', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
        const data = await res.json();
        await showJob(data.job_id);
        await loadJobs();
        setStatus(`Completed job ${data.job_id}.`);
      } catch (error) {
        setStatus(`Audit failed: ${error.message}`);
      }
    }

    async function createUploadJob(event) {
      event.preventDefault();
      setStatus('Uploading and running audit...');
      const form = new FormData(event.target);
      form.set('background', 'false');
      try {
        const res = await apiFetch('/api/audits/upload', { method: 'POST', body: form });
        const data = await res.json();
        await showJob(data.job_id);
        await loadJobs();
        setStatus(`Completed uploaded job ${data.job_id}.`);
      } catch (error) {
        setStatus(`Upload audit failed: ${error.message}`);
      }
    }

    async function inspectPath() {
      setStatus('Inspecting dataset metadata...');
      const data_path = document.getElementById('data_path').value;
      try {
        const res = await apiFetch('/api/inspect/path', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({data_path}) });
        const data = await res.json();
        document.getElementById('inspectOutput').textContent = JSON.stringify(data, null, 2);
        applyInspection(data);
        setStatus('Inspection complete. Suggested metadata keys were applied when available.');
      } catch (error) {
        setStatus(`Inspection failed: ${error.message}`);
      }
    }

    function applyInspection(data) {
      const suggested = data.suggested_keys || {};
      if (suggested.batch_key && !document.getElementById('batch_key').value) document.getElementById('batch_key').value = suggested.batch_key;
      if (suggested.donor_key && !document.getElementById('donor_key').value) document.getElementById('donor_key').value = suggested.donor_key;
      if (suggested.label_key && !document.getElementById('label_key').value) document.getElementById('label_key').value = suggested.label_key;
      const columns = data.obs_columns || [];
      metadataHints.innerHTML = columns.slice(0, 40).map(col => `<span class="hint">${escapeHtml(col)}</span>`).join('');
    }

    async function showJob(jobId) {
      const safeJobId = encodeURIComponent(jobId);
      const res = await apiFetch(`/api/jobs/${safeJobId}/summary`);
      const data = await res.json();
      selectedJobId = jobId;
      summary.innerHTML = [
        metric('Data QC', data.data_qc),
        metric('Signal', data.structural_signal),
        metric('Batch Risk', data.batch_risk),
        metric('Stability', data.stability),
        metric('Trust', data.trust_level),
        metric('Safe', data.safe_to_interpret),
        metric('Main Failure', data.main_failure)
      ].join('');
      links.innerHTML = `
        <a class="link-button" href="/api/jobs/${safeJobId}/report.html" target="_blank">HTML</a>
        <a class="link-button" href="/api/jobs/${safeJobId}/report.pdf" target="_blank">PDF</a>
        <a class="link-button" href="/api/jobs/${safeJobId}/summary.json" target="_blank">JSON</a>
        <a class="link-button" href="/api/jobs/${safeJobId}/evidence_ledger.json" target="_blank">Ledger</a>
        <a class="link-button" href="/api/jobs/${safeJobId}/claim_matrix.json" target="_blank">Claims</a>
      `;
      reportFrame.src = `/api/jobs/${safeJobId}/report.html`;
    }

    async function loadJobs() {
      let rows = [];
      try {
        const res = await apiFetch('/api/jobs');
        rows = await res.json();
      } catch (error) {
        setStatus(`Could not load jobs: ${error.message}`);
      }
      jobsBody.innerHTML = rows.map(row => {
        const summary = row.summary || {};
        return `<div class="job-card" data-job-id="${escapeHtml(row.job_id)}">
          <div><span class="job-label">Job</span><span class="job-value"><code>${escapeHtml(row.job_id)}</code></span></div>
          <div><span class="job-label">Status</span><span class="job-value">${escapeHtml(row.status)}</span></div>
          <div><span class="job-label">Trust</span><span class="job-value">${escapeHtml(summary.trust_level)}</span></div>
          <div><span class="job-label">Safe</span><span class="job-value">${escapeHtml(summary.safe_to_interpret)}</span></div>
          <div><span class="job-label">Main Failure</span><span class="job-value">${escapeHtml(summary.main_failure)}</span></div>
          <div><span class="job-label">Created</span><span class="job-value">${escapeHtml(row.created_at)}</span></div>
        </div>`;
      }).join('');
      jobsBody.querySelectorAll('[data-job-id]').forEach(card => card.addEventListener('click', () => showJob(card.dataset.jobId)));
      if (!selectedJobId && rows.length > 0) {
        await showJob(rows[0].job_id);
      }
    }

    async function loadCaseStudies() {
      try {
        const res = await apiFetch('/api/case-studies');
        const rows = await res.json();
        caseStudies.innerHTML = rows.map(row => `<div class="job-card">
          <div><span class="job-label">Study</span><span class="job-value">${escapeHtml(row.title)}</span></div>
          <div><span class="job-label">ID</span><span class="job-value"><code>${escapeHtml(row.id)}</code></span></div>
          <div><span class="job-label">Claim</span><span class="job-value">${escapeHtml(row.scientific_claim)}</span></div>
          <div><span class="job-label">RUO</span><span class="job-value">${escapeHtml(row.ruo_disclaimer)}</span></div>
        </div>`).join('');
      } catch (error) {
        caseStudies.innerHTML = `<div class="notice">Case studies unavailable: ${escapeHtml(error.message)}</div>`;
      }
    }

    async function runCopilot(event) {
      event.preventDefault();
      setCopilotStatus('understanding request...');
      copilotProgress.innerHTML = '<li>understanding request</li>';
      const form = new FormData(event.target);
      form.set('background', 'false');
      form.set('use_ai', document.getElementById('copilot_use_ai').checked ? 'true' : 'false');
      try {
        const res = await apiFetch('/api/copilot/jobs', { method: 'POST', body: form });
        const job = await res.json();
        const resultRes = await apiFetch(`/api/copilot/jobs/${job.job_id}/result`);
        const result = await resultRes.json();
        showCopilotResult(job, result);
        setCopilotStatus(`completed job ${job.job_id}`);
      } catch (error) {
        setCopilotStatus(`Evidence Copilot failed: ${error.message}`);
      }
    }

    function showCopilotResult(job, result) {
      copilotAnswer.textContent = result.short_answer || valueOrDash(result.status);
      copilotProgress.innerHTML = (job.progress || [result.status]).map(stage => `<li>${escapeHtml(stage)}</li>`).join('');
      showAiInterpretation(result.ai_copilot || {});
      if (result.selected_workflow === 'public_dataset_search') {
        showPublicSearchResult(result);
      } else if (result.selected_workflow === 'de_novo_treatment_response_discovery') {
        showDiscoveryResult(result);
      } else {
        copilotSummary.innerHTML = [
          metric('Workflow', result.selected_workflow),
          metric('Data QC', result.data_qc),
          metric('Signal', result.signal_summary),
          metric('Batch Risk', result.batch_risk),
          metric('Metadata Risk', result.metadata_risk),
          metric('Stability', result.stability),
          metric('Trust', result.trust_verdict),
          metric('Safe', result.safe_to_interpret)
        ].join('');
      }
      const reportLinks = result.report_links || {};
      copilotLinks.innerHTML = [
        reportLinks['report.html'] ? `<a class="link-button" href="/api/copilot/jobs/${job.job_id}/audit/report.html" target="_blank">HTML</a>` : '',
        reportLinks['report.pdf'] ? `<a class="link-button" href="/api/copilot/jobs/${job.job_id}/audit/report.pdf" target="_blank">PDF</a>` : '',
        reportLinks['summary.json'] ? `<a class="link-button" href="/api/copilot/jobs/${job.job_id}/audit/summary.json" target="_blank">Summary</a>` : '',
        `<a class="link-button" href="/api/copilot/jobs/${job.job_id}/plan" target="_blank">Plan</a>`,
        `<a class="link-button" href="/api/copilot/jobs/${job.job_id}/result" target="_blank">Result JSON</a>`
      ].join('');
      const can = result.what_can_be_claimed || [];
      const cannot = result.what_cannot_be_claimed || [];
      copilotClaims.innerHTML = `
        <tr><th>What can be claimed</th><td>${can.map(item => `<div>${escapeHtml(item)}</div>`).join('')}</td></tr>
        <tr><th>What cannot be claimed</th><td>${cannot.map(item => `<div>${escapeHtml(item)}</div>`).join('')}</td></tr>
        <tr><th>RUO</th><td>${escapeHtml(result.ruo_disclaimer)}</td></tr>
      `;
    }

    function showAiInterpretation(ai) {
      const planning = ai.planning || {};
      const interpretation = ai.interpretation || {};
      if (planning.status !== 'completed' && interpretation.status !== 'completed') {
        aiInterpretationSection.style.display = 'none';
        return;
      }
      aiInterpretationSection.style.display = 'block';
      const supporting = interpretation.evidence_supporting || [];
      const limiting = interpretation.evidence_limiting || [];
      aiInterpretation.innerHTML = `
        <div class="candidate-meta">
          ${candidateField('Model', interpretation.model || planning.model)}
          ${candidateField('Intent', planning.analysis_intent)}
          ${candidateField('Suggested Workflow', planning.suggested_workflow)}
          ${candidateField('Claim Status', interpretation.claim_status)}
        </div>
        <p>${escapeHtml(interpretation.executive_summary)}</p>
        ${supporting.length ? `<div><strong>Supporting evidence</strong><br>${supporting.map(escapeHtml).join('<br>')}</div>` : ''}
        ${limiting.length ? `<div style="margin-top:8px"><strong>Limiting evidence</strong><br>${limiting.map(escapeHtml).join('<br>')}</div>` : ''}
        ${interpretation.next_validation_step ? `<div style="margin-top:8px"><strong>Next validation step</strong><br>${escapeHtml(interpretation.next_validation_step)}</div>` : ''}
        <div class="muted" style="margin-top:8px">Statistics authority: deterministic OmicsTrust engine. No raw expression data sent.</div>
      `;
    }

    function showDiscoveryResult(result) {
      const stats = result.statistics || {};
      const summary = result.dataset_summary || {};
      copilotSummary.innerHTML = [
        metric('Workflow', result.selected_workflow),
        metric('Status', result.status),
        metric('Top Axis', result.top_candidate_axis),
        metric('Interaction', result.interaction_term),
        metric('OR / 1 SD', result.OR),
        metric('Wald p', result.wald_p),
        metric('LRT p', result.lrt_p),
        metric('FDR', result.fdr),
        metric('Permutation p', result.permutation_p),
        metric('Bootstrap Stability', result.bootstrap_direction_stability),
        metric('Metadata R2', result.metadata_r2),
        metric('Patients', summary.n_patients),
        metric('Features', summary.n_features),
        metric('Validation Required', result.validation_required ? 'yes' : 'no'),
        metric('Clinical Use', result.clinical_use_allowed ? 'allowed' : 'not allowed')
      ].join('') + discoverySubgroups(stats.subgroup_descriptive_summary || result.subgroup_mortality || []);
    }

    function discoverySubgroups(rows) {
      if (!rows.length) return '';
      return `
        <section class="candidate-list">
          <h3>Subgroup descriptive summary</h3>
          ${rows.map(row => `
            <article class="candidate-card">
              <strong>${escapeHtml(row.candidate_endotype)}</strong>
              <div class="candidate-meta">
                ${candidateField('Treatment', row.vasopressor || row.treatment)}
                ${candidateField('Count', row.count)}
                ${candidateField('Events', row.sum)}
                ${candidateField('Event Rate', row.mean)}
              </div>
            </article>
          `).join('')}
        </section>
      `;
    }

    function showPublicSearchResult(result) {
      const high = result.high_suitability_candidates || [];
      const medium = result.medium_suitability_candidates || [];
      const weak = result.weak_literature_leads || [];
      const candidates = result.candidates || [];
      const compact = !!result.compact_mode;
      const strategy = searchStrategySection(result.search_strategy || {});
      const sections = [];
      if (high.length) sections.push(candidateSection('High suitability candidates', high, compact));
      if (medium.length) sections.push(candidateSection('Medium suitability candidates', medium, compact));
      if (weak.length) sections.push(candidateSection('Weak literature leads', weak, compact));
      if (!sections.length) {
        copilotSummary.innerHTML = [
          metric('Workflow', result.selected_workflow),
          metric('Status', result.final_status || result.status),
          metric('Candidates', 0),
          metric('Weak Leads', 0),
          metric('Next Action', result.next_best_action)
        ].join('') + strategy;
        return;
      }
      copilotSummary.innerHTML = [
        metric('Workflow', result.selected_workflow),
        metric('Status', result.final_status || result.status),
        metric('Candidates', candidates.length),
        metric('Weak Leads', weak.length)
      ].join('') + strategy + sections.join('');
    }

    function searchStrategySection(strategy) {
      const parsed = strategy.parsed || {};
      const queries = strategy.queries_run || [];
      const rejected = strategy.why_candidates_were_rejected || [];
      const suggestions = strategy.suggested_refined_queries || [];
      return `
        <details class="notice" open>
          <summary><strong>Search strategy</strong></summary>
          <div class="candidate-meta">
            ${candidateField('Explicit Disease', (parsed.disease_terms_explicit || []).join(', '))}
            ${candidateField('Expanded Disease', (parsed.disease_terms_expanded || []).join(', '))}
            ${candidateField('Explicit Treatment', (parsed.treatment_terms_explicit || []).join(', '))}
            ${candidateField('Expanded Treatment', (parsed.treatment_terms_expanded || []).join(', '))}
            ${candidateField('Response Terms', (parsed.response_terms || []).join(', '))}
            ${candidateField('Omics Terms', (parsed.omics_terms || []).join(', '))}
            ${candidateField('Sample Terms', (parsed.sample_terms || []).join(', '))}
            ${candidateField('Excluded Diseases', (parsed.excluded_diseases || []).join(', '))}
            ${candidateField('Excluded Treatments', (parsed.excluded_treatments || []).join(', '))}
            ${candidateField('Excluded Contexts', (parsed.excluded_contexts || []).join(', '))}
            ${candidateField('Sources', (strategy.sources_searched || []).join(', '))}
            ${candidateField('Raw Hits', JSON.stringify(strategy.raw_hits_by_source || {}))}
            ${candidateField('Kept', strategy.candidates_kept)}
            ${candidateField('Excluded', strategy.excluded_count)}
          </div>
          <div class="notice">${queries.slice(0, 12).map(q => `• ${escapeHtml(q)}`).join('\\n') || 'No query strings recorded.'}</div>
          ${rejected.length ? `<div class="notice">Rejected: ${rejected.map(item => `${escapeHtml(item.reason)} (${escapeHtml(item.count)})`).join(', ')}</div>` : ''}
          ${suggestions.length ? `<div class="notice">Refine: ${suggestions.map(escapeHtml).join('\\n')}</div>` : ''}
        </details>
      `;
    }

    function candidateSection(title, candidates, compact=false) {
      return `<div class="notice"><strong>${title}</strong></div>` + candidates.map(candidate => `
        <div class="candidate-card">
          <h3>${escapeHtml(candidate.accession_id)}: ${escapeHtml(candidate.title)}</h3>
          <div class="badges">
            <span class="badge">${escapeHtml(candidate.suitability_category || title)}</span>
            <span class="badge">${escapeHtml(candidate.source_confidence || 'metadata')}</span>
            ${candidate.source === 'local_reference_registry' ? '<span class="badge">Fallback reference</span>' : ''}
            <span class="badge">Metadata only</span>
            <span class="badge">No download performed</span>
            <span class="badge">RUO</span>
          </div>
          ${compact ? `<div class="notice">Score ${escapeHtml(candidate.suitability_score)} · ${escapeHtml(candidate.source)} · ${escapeHtml((candidate.limitations || [])[0] || 'Review source metadata before download or audit.')}</div>` : `
          <div class="candidate-meta">
            ${candidateField('Source', candidate.source)}
            ${candidateField('Metadata', candidate.metadata_source)}
            ${candidateField('Disease Match', candidate.disease_match)}
            ${candidateField('Treatment Match', candidate.treatment_match)}
            ${candidateField('Samples', candidate.sample_count)}
            ${candidateField('Omics', candidate.omics_type)}
            ${candidateField('Treatment Labels', candidate.treatment_label_likelihood)}
            ${candidateField('Response Labels', candidate.response_label_likelihood)}
            ${candidateField('Baseline', candidate.baseline_or_pretreatment_evidence ? 'likely' : 'unclear')}
            ${candidateField('Score', candidate.suitability_score)}
          </div>
          <div class="notice">${(candidate.limitations || []).map(escapeHtml).join('\\n') || 'No limitations extracted from metadata summary.'}</div>
          `}
          <div class="buttons">
            <a class="link-button" href="${escapeHtml(safeExternalUrl(candidate.url))}" target="_blank" rel="noopener noreferrer">Source</a>
          </div>
        </div>
      `).join('');
    }

    function candidateField(label, value) {
      return `<div class="candidate-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
    }

    function saveToken() {
      const token = apiTokenInput.value.trim();
      if (token) {
        localStorage.setItem('omicstrust_token', token);
        document.cookie = `omicstrust_token=${encodeURIComponent(token)}; path=/; SameSite=Strict`;
      } else {
        localStorage.removeItem('omicstrust_token');
        document.cookie = 'omicstrust_token=; path=/; Max-Age=0; SameSite=Strict';
      }
      setStatus(token ? 'API token saved for this browser.' : 'API token cleared.');
      loadJobs();
      loadCaseStudies();
    }

    document.getElementById('pathForm').addEventListener('submit', createPathJob);
    document.getElementById('uploadForm').addEventListener('submit', createUploadJob);
    document.getElementById('inspectPath').addEventListener('click', inspectPath);
    document.getElementById('refreshJobs').addEventListener('click', loadJobs);
    document.getElementById('saveToken').addEventListener('click', saveToken);
    document.getElementById('copilotForm').addEventListener('submit', runCopilot);
    document.querySelectorAll('.tab-button').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
    apiTokenInput.value = apiToken();
    loadHealth();
    loadJobs();
    loadCaseStudies();
  </script>
</body>
</html>"""
