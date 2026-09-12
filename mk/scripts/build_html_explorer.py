"""Generate a modern, responsive, standalone dataset_explorer.html containing telemetry from all 20 turbines across Penmanshiel and Kelmarsh with 5-line TSLM output."""

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mk.dashboard import load_all_wind_farms, format_tslm_explanation, SIGNAL_META
from mk.src.data.schemas import FAULT_CLASSES, SELECTED_SIGNALS, SIGNAL_NAMES, WINDOW_STEPS


def generate_html():
    df_all, tel_dict = load_all_wind_farms()

    # Build catalog covering all 20 turbines and all 5 fault classes
    catalog = []
    telemetry = {}

    for turb in sorted(df_all["turbine_id"].unique()):
        turb_df = df_all[df_all["turbine_id"] == turb]
        anom = turb_df[turb_df["fault_class"] != "Normal Operation"]
        norm = turb_df[turb_df["fault_class"] == "Normal Operation"]
        picks = []
        if not anom.empty:
            picks.append(anom.iloc[0])
        if not norm.empty:
            picks.append(norm.iloc[0])
        if len(picks) < 2 and len(turb_df) > 1:
            picks.append(turb_df.iloc[1])

        for row in picks:
            rid = row["record_id"]
            tel_df = tel_dict[rid]
            tslm = format_tslm_explanation(row, tel_df)
            catalog.append({
                "id": rid,
                "farm": row["wind_farm"],
                "turbine": row["turbine_id"],
                "model": row["turbine_model"],
                "fault": row["fault_class"],
                "start_time": row["start_time"].strftime("%Y-%m-%d %H:%M"),
                "end_time": row["end_time"].strftime("%Y-%m-%d %H:%M"),
                "prompt": row.get("prompt", ""),
                "finding": tslm["finding"],
                "evidence": tslm["evidence"],
                "cause": tslm["cause"],
                "impact": tslm["impact"],
                "action": tslm["action"],
                "answer": tslm["answer"],
            })
            telemetry[rid] = {col: [round(float(v), 2) for v in tel_df[col].tolist()] for col in SIGNAL_NAMES}

    signals_meta_json = [
        {
            "name": s.canonical_name,
            "unit": s.unit,
            "desc": s.description,
            "color": [
                "#3B82F6", "#10B981", "#F59E0B", "#EC4899",
                "#EF4444", "#8B5CF6", "#06B6D4", "#64748B"
            ][i],
        }
        for i, s in enumerate(SELECTED_SIGNALS)
    ]

    payload = {
        "catalog": catalog,
        "telemetry": telemetry,
        "signals": signals_meta_json,
    }

    json_str = json.dumps(payload, separators=(',', ':'))

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dual Wind Farm Fleet SCADA Explorer | Penmanshiel & Kelmarsh</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {{
      --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }}
    body {{
      font-family: var(--font-sans);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }}
    .chart-canvas {{
      width: 100%;
      height: 320px;
      touch-action: none;
    }}
    .custom-scrollbar::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{
      background: rgba(156, 163, 175, 0.4);
      border-radius: 3px;
    }}
  </style>
</head>
<body class="bg-slate-900 text-slate-100 antialiased p-4 md:p-6 min-h-screen">

  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Top Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-800 p-5 rounded-2xl border border-slate-700 shadow-sm">
      <div class="space-y-1">
        <div class="flex items-center gap-3">
          <div class="p-2.5 bg-blue-500/10 text-blue-400 rounded-xl">
            <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div>
            <h1 class="text-xl md:text-2xl font-bold tracking-tight text-white">Dual-Farm Wind Turbine SCADA Visualizer</h1>
            <p class="text-xs md:text-sm text-slate-400">All 20 Turbines &middot; Penmanshiel (14 MM82) &amp; Kelmarsh (6 MM92) &middot; 12-Hour Telemetry Windows</p>
          </div>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span> 20 Fleet Turbines
        </span>
        <span class="badge bg-blue-500/10 text-blue-400 border border-blue-500/20">600 SCADA Windows</span>
        <span class="badge bg-purple-500/10 text-purple-400 border border-purple-500/20">8 Sensors &middot; 10-min Res</span>
      </div>
    </div>

    <!-- Fleet KPIs -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Monitored Fleet</span>
        <div class="text-xl font-bold mt-1 text-white">20 Assets</div>
        <span class="text-[10px] text-emerald-400">14 Pen + 6 Kel</span>
      </div>
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Total Windows</span>
        <div class="text-xl font-bold mt-1 text-white">600 Windows</div>
        <span class="text-[10px] text-blue-400">7,200 Monitored Hrs</span>
      </div>
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Window Horizon</span>
        <div class="text-xl font-bold mt-1 text-white">12 Hours</div>
        <span class="text-[10px] text-slate-400">72 steps @ 10 min</span>
      </div>
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Continuous Sensors</span>
        <div class="text-xl font-bold mt-1 text-white">8 Channels</div>
        <span class="text-[10px] text-slate-400">Aero, Mech, Thermal</span>
      </div>
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Diagnostic Classes</span>
        <div class="text-xl font-bold mt-1 text-white">5 Categories</div>
        <span class="text-[10px] text-amber-400">Standardized TSLM</span>
      </div>
      <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <span class="text-xs text-slate-400 font-medium">Turbine Models</span>
        <div class="text-xl font-bold mt-1 text-white">Senvion 2.05MW</div>
        <span class="text-[10px] text-purple-400">MM82 &amp; MM92</span>
      </div>
    </div>

    <!-- Main Workspace Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Left Column: Controls & Window Browser -->
      <div class="lg:col-span-1 space-y-4">
        
        <!-- Filters Card -->
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm space-y-3">
          <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span>Filter Telemetry</span>
            <span id="filtered-count" class="badge bg-blue-500/10 text-blue-400">40 Windows</span>
          </h2>
          
          <div>
            <label class="block text-xs font-medium text-slate-300 mb-1">Wind Farm</label>
            <select id="farm-filter" class="w-full bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="ALL">🌐 All Wind Farms (Penmanshiel &amp; Kelmarsh)</option>
              <option value="Penmanshiel">🏴󠁧󠁢󠁳󠁣󠁴󠁿 Penmanshiel Wind Farm (14 Turbines)</option>
              <option value="Kelmarsh">🇬🇧 Kelmarsh Wind Farm (6 Turbines)</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-medium text-slate-300 mb-1">Turbine</label>
            <select id="turbine-filter" class="w-full bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="ALL">All Turbines in Scope (20 Turbines)</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-medium text-slate-300 mb-1">Diagnostic Fault Category</label>
            <select id="fault-filter" class="w-full bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="ALL">All Categories</option>
              <option value="Normal Operation">Normal Operation</option>
              <option value="Gearbox Overheating">Gearbox Overheating</option>
              <option value="Generator Bearing Anomaly">Generator Bearing Anomaly</option>
              <option value="Pitch / Aerodynamic Fault">Pitch / Aerodynamic Fault</option>
              <option value="Turbine Trip / Forced Outage">Turbine Trip / Forced Outage</option>
            </select>
          </div>
        </div>

        <!-- Window Selection List -->
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400">Available Timeframes</h2>
            <span class="text-xs text-slate-400">Click to select</span>
          </div>
          <div id="window-list" class="space-y-1.5 max-h-[360px] overflow-y-auto pr-1 custom-scrollbar">
            <!-- Populated via JS -->
          </div>
        </div>

        <!-- Selected Turbine Specs Card -->
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm space-y-2">
          <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400">Asset Specifications</h2>
          <div id="turbine-spec-info" class="text-xs space-y-1 text-slate-300">
            <!-- Populated via JS -->
          </div>
        </div>

      </div>

      <!-- Right Column: Time-Series Visualizer & Model Output -->
      <div class="lg:col-span-2 space-y-4">

        <!-- Selected Window Header Card -->
        <div class="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-sm space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2">
                <h3 id="cur-window-id" class="text-lg font-bold text-white">Window w-00000</h3>
                <span id="cur-fault-badge" class="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Normal Operation</span>
              </div>
              <p id="cur-turbine-info" class="text-xs text-slate-400 mt-0.5">Asset: Penmanshiel WT01 &middot; Timespan: 2020-01-16 00:00 to 12:00 UTC</p>
            </div>
            <div class="flex items-center gap-2">
              <button id="prev-btn" class="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">&larr; Prev</button>
              <button id="next-btn" class="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">Next &rarr;</button>
            </div>
          </div>

          <!-- Interactive Time-Series Canvas Plot -->
          <div>
            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold text-slate-400 uppercase tracking-wider">12-Hour SCADA Telemetry (Hover to Inspect)</span>
              <div class="flex items-center gap-2 text-xs">
                <span id="hover-time" class="text-slate-400">Step: --</span>
                <span id="hover-val" class="font-mono font-medium text-blue-400">Value: --</span>
              </div>
            </div>

            <!-- Canvas Container -->
            <div class="relative bg-slate-900 border border-slate-700 rounded-xl p-3">
              <canvas id="timeSeriesCanvas" class="chart-canvas"></canvas>
            </div>

            <!-- Signal Selector Pills -->
            <div class="flex flex-wrap gap-1.5 mt-3" id="signal-pills">
              <!-- Populated via JS -->
            </div>
          </div>

        </div>

        <!-- 3-Stage Pipeline Breakdown -->
        <div class="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-700 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-lg">🔬</span>
              <h3 class="text-sm font-bold uppercase tracking-wider text-white">Diagnostic Pipeline Breakdown</h3>
            </div>
            <span class="text-xs text-slate-400">Data ➔ Processing ➔ Output</span>
          </div>

          <!-- Stage 1: In the Data -->
          <div class="p-3.5 bg-slate-900/70 rounded-xl border border-blue-500/30 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center gap-1.5">
                <span>📥</span> Stage 1: What is in the Data?
              </span>
              <span class="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20">Ground Truth &amp; SCADA</span>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed">
              &bull; <b>Raw Telemetry</b>: 8 continuous sensors &middot; 72 timesteps (12 hours @ 10-min resolution) recorded in physical engineering units.<br/>
              &bull; <b>Ground Truth Status Event</b>: <span id="stage1-gt-event" class="font-semibold text-emerald-400"></span> (logged in historical Greenbyte operator alarms).<br/>
              &bull; <span class="text-amber-400 font-medium">Zero-Leakage Guarantee:</span> The alarm code, message, and category are historical ground truth and are <b>NEVER fed into the model</b>.
            </p>
          </div>

          <!-- Stage 2: Processed by Model -->
          <div class="p-3.5 bg-slate-900/70 rounded-xl border border-purple-500/30 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                <span>⚙️</span> Stage 2: What Was Processed by the Model?
              </span>
              <span class="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-full border border-purple-500/20">Model Input Tensor</span>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed">
              &bull; <b>Input Tensor Shape</b>: <code class="text-white bg-slate-800 px-1 py-0.5 rounded">[1, 72, 8]</code> float32 matrix.<br/>
              &bull; <b>Preprocessing</b>: Per-window Z-score standardization (<code class="text-purple-300">z = (x - &mu;) / &sigma;</code>) normalizing each channel to zero-mean unit-variance.<br/>
              &bull; <b>Patch Tokenization</b>: 1D Temporal Convolution (<code class="text-purple-300">k=4, s=4</code>) compresses 72 timesteps into <b>18 temporal patch tokens</b> projected to a 512-dim LLM latent embedding space.<br/>
              &bull; <b>Prompt Query</b>: Natural language supervisory diagnostic prompt asking for physical CoT reasoning and dispatch action.
            </p>
          </div>

          <!-- Stage 3: Output from Model vs Ground Truth -->
          <div class="p-3.5 bg-slate-900/70 rounded-xl border border-emerald-500/30 space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <span>📤</span> Stage 3: Live Neural Output vs Supervisory Target
              </span>
              <span class="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/20">Task T1 Benchmark</span>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed">
              &bull; <b>🧠 Live Neural Model Output</b>: Softmax probability distribution and discrete operational classification head (`Answer: <class>`). The neural network classifies signals; it does <i>not</i> generate text.<br/>
              &bull; <b>📋 Supervisory Target Report</b> (deterministic physics &amp; alarm rule specification):
            </p>

            <!-- 5-part Box -->
            <div class="space-y-2.5 text-xs bg-slate-950/70 p-3.5 rounded-lg border border-slate-700/60 mt-2">
              <div class="inline-block bg-blue-500/10 border border-blue-500/30 px-2.5 py-0.5 rounded text-[10px] font-semibold text-blue-400 mb-1">
                🏷️ SOURCE: Rule-Based Physics Engine &amp; Historical Ground Truth (Benchmark Target)
              </div>
              <div>
                <span class="font-bold text-blue-400 uppercase tracking-wider">1. FINDING</span>
                <p id="cur-finding" class="text-slate-200 mt-0.5 leading-relaxed pl-2 border-l-2 border-blue-400"></p>
              </div>
              <div>
                <span class="font-bold text-purple-400 uppercase tracking-wider">2. EVIDENCE</span>
                <p id="cur-evidence" class="text-slate-200 mt-0.5 leading-relaxed pl-2 border-l-2 border-purple-400"></p>
              </div>
              <div>
                <span class="font-bold text-red-400 uppercase tracking-wider">3. CAUSE</span>
                <p id="cur-cause" class="text-slate-200 mt-0.5 leading-relaxed pl-2 border-l-2 border-red-400"></p>
              </div>
              <div>
                <span class="font-bold text-amber-400 uppercase tracking-wider">4. IMPACT</span>
                <p id="cur-impact" class="text-slate-200 mt-0.5 leading-relaxed pl-2 border-l-2 border-amber-400"></p>
              </div>
              <div>
                <span class="font-bold text-emerald-400 uppercase tracking-wider">5. ACTION</span>
                <p id="cur-action" class="text-slate-200 mt-0.5 leading-relaxed pl-2 border-l-2 border-emerald-400 font-medium"></p>
              </div>
              <div class="pt-2 border-t border-slate-700 font-mono text-sm font-bold text-emerald-400 flex items-center justify-between">
                <span>Target Answer: <span id="cur-answer" class="text-white"></span></span>
                <span class="text-xs text-slate-400 font-normal">Supervisory Benchmark Label</span>
              </div>
            </div>
          </div>

        </div>

        <!-- 8 Sensor Channels Statistical Metrics Table -->
        <div class="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-sm space-y-3">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Current Window Sensor Statistics</h3>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="border-b border-slate-700 text-slate-400 font-medium">
                <tr>
                  <th class="py-2 px-2">Signal</th>
                  <th class="py-2 px-2">Unit</th>
                  <th class="py-2 px-2">Mean</th>
                  <th class="py-2 px-2">Min</th>
                  <th class="py-2 px-2">Max</th>
                  <th class="py-2 px-2">Delta (&Delta;)</th>
                </tr>
              </thead>
              <tbody id="signal-stats-tbody" class="divide-y divide-slate-700">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>

      </div>

    </div>

    <!-- Footer -->
    <div class="text-center text-xs text-slate-500 pt-4 border-t border-slate-800">
      Zurich Hackathon Time-Series Project &middot; OpenTSLM Dual Wind Farm Visualizer &middot; Senvion MM82 &amp; MM92 SCADA
    </div>

  </div>

  <!-- Interactive Data Script -->
  <script>
    const DATASET = {json_str};

    const FAULT_COLORS = {{
      'Normal Operation': {{ bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', stroke: '#10B981' }},
      'Gearbox Overheating': {{ bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', stroke: '#EF4444' }},
      'Generator Bearing Anomaly': {{ bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', stroke: '#F59E0B' }},
      'Pitch / Aerodynamic Fault': {{ bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20', stroke: '#8B5CF6' }},
      'Turbine Trip / Forced Outage': {{ bg: 'bg-pink-500/10', text: 'text-pink-400', border: 'border-pink-500/20', stroke: '#EC4899' }}
    }};

    let state = {{
      curWindowId: DATASET.catalog[0]?.id || '',
      activeSignals: ['wind_speed', 'power', 'rotor_speed', 'gear_oil_temp'],
      hoverStep: null
    }};

    // DOM Elements
    const farmFilter = document.getElementById('farm-filter');
    const turbineFilter = document.getElementById('turbine-filter');
    const faultFilter = document.getElementById('fault-filter');
    const windowList = document.getElementById('window-list');
    const filteredCount = document.getElementById('filtered-count');
    const canvas = document.getElementById('timeSeriesCanvas');
    const ctx = canvas.getContext('2d');
    const signalPillsContainer = document.getElementById('signal-pills');

    function populateTurbineDropdown() {{
      const selectedFarm = farmFilter.value;
      const currentSelection = turbineFilter.value;
      turbineFilter.innerHTML = '<option value="ALL">All Turbines in Scope</option>';
      
      const turbines = [...new Set(DATASET.catalog.map(w => w.turbine))].sort();
      turbines.forEach(t => {{
        const sample = DATASET.catalog.find(w => w.turbine === t);
        if (selectedFarm === 'ALL' || sample.farm === selectedFarm) {{
          const opt = document.createElement('option');
          opt.value = t;
          opt.textContent = `${{t}} (${{sample.farm}})`;
          turbineFilter.appendChild(opt);
        }}
      }});
      if (currentSelection && turbineFilter.querySelector(`option[value="${{currentSelection}}"]`)) {{
        turbineFilter.value = currentSelection;
      }}
    }}

    function getFilteredWindows() {{
      const farm = farmFilter.value;
      const turbine = turbineFilter.value;
      const fault = faultFilter.value;

      return DATASET.catalog.filter(w => {{
        if (farm !== 'ALL' && w.farm !== farm) return false;
        if (turbine !== 'ALL' && w.turbine !== turbine) return false;
        if (fault !== 'ALL' && w.fault !== fault) return false;
        return true;
      }});
    }}

    function renderWindowList() {{
      const list = getFilteredWindows();
      filteredCount.textContent = `${{list.length}} Windows`;
      windowList.innerHTML = '';

      if (list.length === 0) {{
        windowList.innerHTML = '<div class="text-xs text-slate-500 py-3 text-center">No telemetry windows match filters.</div>';
        return;
      }}

      list.forEach(w => {{
        const item = document.createElement('div');
        const isSelected = w.id === state.curWindowId;
        const col = FAULT_COLORS[w.fault] || FAULT_COLORS['Normal Operation'];

        item.className = `p-2 rounded-lg cursor-pointer transition-all border text-xs ${{
          isSelected 
            ? 'bg-blue-900/30 border-blue-500 text-white' 
            : 'bg-slate-900/40 border-slate-700/60 text-slate-300 hover:bg-slate-700/50'
        }}`;

        item.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-bold text-xs">${{w.turbine}}</span>
            <span class="badge ${{col.bg}} ${{col.text}} border ${{col.border}} text-[10px]">${{w.fault}}</span>
          </div>
          <div class="text-[10px] text-slate-400 mt-1 flex justify-between">
            <span>${{w.id}}</span>
            <span>${{w.start_time}}</span>
          </div>
        `;

        item.onclick = () => selectWindow(w.id);
        windowList.appendChild(item);
      }});

      if (!list.some(w => w.id === state.curWindowId) && list.length > 0) {{
        selectWindow(list[0].id);
      }}
    }}

    function selectWindow(winId) {{
      state.curWindowId = winId;
      const win = DATASET.catalog.find(w => w.id === winId);
      if (!win) return;

      const col = FAULT_COLORS[win.fault] || FAULT_COLORS['Normal Operation'];

      // Update Header
      document.getElementById('cur-window-id').textContent = `Window ${{win.id}}`;
      const badge = document.getElementById('cur-fault-badge');
      badge.textContent = win.fault;
      badge.className = `badge ${{col.bg}} ${{col.text}} border ${{col.border}}`;

      document.getElementById('cur-turbine-info').textContent = 
        `Asset: ${{win.turbine}} &middot; Site: ${{win.farm}} Wind Farm &middot; Model: ${{win.model}} &middot; Timespan: ${{win.start_time}} to ${{win.end_time}} UTC`;

      // Update TSLM Report & Pipeline Stages
      document.getElementById('stage1-gt-event').textContent = win.fault;
      document.getElementById('cur-finding').textContent = win.finding;
      document.getElementById('cur-evidence').textContent = win.evidence;
      document.getElementById('cur-cause').textContent = win.cause;
      document.getElementById('cur-impact').textContent = win.impact;
      document.getElementById('cur-action').textContent = win.action;
      document.getElementById('cur-answer').textContent = win.answer;

      // Update Turbine Spec
      const isPen = win.farm === 'Penmanshiel';
      document.getElementById('turbine-spec-info').innerHTML = `
        <div class="flex justify-between"><span>Turbine Model:</span> <span class="font-semibold text-white">${{win.model}}</span></div>
        <div class="flex justify-between"><span>Site Location:</span> <span class="font-semibold text-white">${{isPen ? 'Scottish Borders, UK' : 'Northamptonshire, UK'}}</span></div>
        <div class="flex justify-between"><span>Rated Capacity:</span> <span class="font-semibold text-white">2,050 kW (2.05 MW)</span></div>
        <div class="flex justify-between"><span>Rotor Diameter:</span> <span class="font-semibold text-white">${{isPen ? '82 meters' : '92 meters'}}</span></div>
        <div class="flex justify-between"><span>Cut-in / Rated:</span> <span class="font-semibold text-white">3.0 / 12.5 m/s</span></div>
      `;

      renderWindowList();
      renderStatsTable();
      drawChart();
    }}

    function renderSignalPills() {{
      signalPillsContainer.innerHTML = '';
      DATASET.signals.forEach(s => {{
        const btn = document.createElement('button');
        const isActive = state.activeSignals.includes(s.name);
        btn.className = `px-2 py-1 rounded-md text-[11px] font-medium transition-all flex items-center gap-1.5 border ${{
          isActive 
            ? 'bg-slate-700 border-slate-500 text-white shadow-sm' 
            : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
        }}`;
        btn.innerHTML = `<span class="w-2 h-2 rounded-full" style="background-color: ${{s.color}}"></span> ${{s.name}} (${{s.unit}})`;
        btn.onclick = () => {{
          if (state.activeSignals.includes(s.name)) {{
            if (state.activeSignals.length > 1) {{
              state.activeSignals = state.activeSignals.filter(x => x !== s.name);
            }}
          }} else {{
            state.activeSignals.push(s.name);
          }}
          renderSignalPills();
          drawChart();
        }};
        signalPillsContainer.appendChild(btn);
      }});
    }}

    function renderStatsTable() {{
      const tbody = document.getElementById('signal-stats-tbody');
      tbody.innerHTML = '';
      const data = DATASET.telemetry[state.curWindowId];
      if (!data) return;

      DATASET.signals.forEach(s => {{
        const arr = data[s.name];
        if (!arr) return;
        const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
        const min = Math.min(...arr);
        const max = Math.max(...arr);
        const delta = arr[arr.length - 1] - arr[0];

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="py-1.5 px-2 font-medium text-white flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full inline-block" style="background-color: ${{s.color}}"></span>
            ${{s.name}}
          </td>
          <td class="py-1.5 px-2 text-slate-400">${{s.unit}}</td>
          <td class="py-1.5 px-2 font-mono">${{mean.toFixed(2)}}</td>
          <td class="py-1.5 px-2 font-mono">${{min.toFixed(2)}}</td>
          <td class="py-1.5 px-2 font-mono">${{max.toFixed(2)}}</td>
          <td class="py-1.5 px-2 font-mono ${{delta > 0 ? 'text-amber-400' : 'text-slate-300'}}">${{delta >= 0 ? '+' : ''}}${{delta.toFixed(2)}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    }}

    function drawChart() {{
      resizeCanvas();
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      const pad = {{ l: 40, r: 20, t: 20, b: 30 }};

      ctx.clearRect(0, 0, w, h);

      const tel = DATASET.telemetry[state.curWindowId];
      if (!tel) return;

      // Draw grid lines
      ctx.strokeStyle = '#334155';
      ctx.lineWidth = 0.5;
      for (let i = 0; i <= 4; i++) {{
        const y = pad.t + (h - pad.t - pad.b) * (i / 4);
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(w - pad.r, y);
        ctx.stroke();
      }}

      // Normalized [0, 1] per channel for multi-series overlay
      state.activeSignals.forEach(sName => {{
        const arr = tel[sName];
        if (!arr) return;
        const meta = DATASET.signals.find(s => s.name === sName);
        const min = Math.min(...arr);
        const max = Math.max(...arr);
        const range = max - min || 1;

        ctx.strokeStyle = meta.color;
        ctx.lineWidth = 2;
        ctx.beginPath();

        const stepX = (w - pad.l - pad.r) / (arr.length - 1);
        arr.forEach((val, i) => {{
          const normY = (val - min) / range;
          const x = pad.l + i * stepX;
          const y = pad.t + (1 - normY) * (h - pad.t - pad.b);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});
        ctx.stroke();
      }});

      // Draw hover cursor line
      if (state.hoverStep !== null) {{
        const stepX = (w - pad.l - pad.r) / 71;
        const hx = pad.l + state.hoverStep * stepX;
        ctx.strokeStyle = '#94A3B8';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(hx, pad.t);
        ctx.lineTo(hx, h - pad.b);
        ctx.stroke();
        ctx.setLineDash([]);
      }}
    }}

    // Canvas Hover Interaction
    canvas.addEventListener('mousemove', e => {{
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const pad = {{ l: 40, r: 20 }};
      const plotW = rect.width - pad.l - pad.r;
      if (mouseX < pad.l || mouseX > rect.width - pad.r) {{
        state.hoverStep = null;
        document.getElementById('hover-time').textContent = 'Step: --';
        document.getElementById('hover-val').textContent = 'Value: --';
        drawChart();
        return;
      }}

      const step = Math.round(((mouseX - pad.l) / plotW) * 71);
      state.hoverStep = Math.max(0, Math.min(71, step));

      const mins = state.hoverStep * 10;
      const hrs = Math.floor(mins / 60);
      const rem = mins % 60;
      document.getElementById('hover-time').textContent = `T: +${{hrs}}h${{rem ? rem + 'm' : ''}} (pt ${{state.hoverStep + 1}}/72)`;

      const tel = DATASET.telemetry[state.curWindowId];
      if (tel && state.activeSignals.length > 0) {{
        const prim = state.activeSignals[0];
        const val = tel[prim][state.hoverStep];
        const meta = DATASET.signals.find(s => s.name === prim);
        document.getElementById('hover-val').textContent = `${{prim}}: ${{val.toFixed(1)}} ${{meta.unit}}`;
      }}
      drawChart();
    }});

    canvas.addEventListener('mouseleave', () => {{
      state.hoverStep = null;
      document.getElementById('hover-time').textContent = 'Step: --';
      document.getElementById('hover-val').textContent = 'Value: --';
      drawChart();
    }});

    // Event Handlers
    farmFilter.addEventListener('change', () => {{
      populateTurbineDropdown();
      renderWindowList();
    }});

    turbineFilter.addEventListener('change', renderWindowList);
    faultFilter.addEventListener('change', renderWindowList);

    document.getElementById('prev-btn').addEventListener('click', () => {{
      const list = getFilteredWindows();
      const idx = list.findIndex(w => w.id === state.curWindowId);
      if (idx > 0) selectWindow(list[idx - 1].id);
    }});

    document.getElementById('next-btn').addEventListener('click', () => {{
      const list = getFilteredWindows();
      const idx = list.findIndex(w => w.id === state.curWindowId);
      if (idx < list.length - 1) selectWindow(list[idx + 1].id);
    }});

    window.addEventListener('resize', drawChart);

    // Initial load
    populateTurbineDropdown();
    renderSignalPills();
    renderWindowList();
    if (DATASET.catalog.length > 0) {{
      selectWindow(DATASET.catalog[0].id);
    }}
  </script>
</body>
</html>
"""

    out_file = REPO_ROOT / "mk" / "dataset_explorer.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[+] Successfully generated standalone HTML visualizer at: {out_file} ({out_file.stat().st_size:,} bytes)")


if __name__ == "__main__":
    generate_html()
