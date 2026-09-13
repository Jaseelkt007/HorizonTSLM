import Link from "next/link";

import Explanation from "@/components/Explanation";
import FleetMap from "@/components/FleetMap";
import { IconArrow } from "@/components/Icons";
import OperatorTriageQueue from "@/components/OperatorTriageQueue";
import styles from "@/components/Overview.module.css";
import SignalPanels from "@/components/SignalPanels";
import { allSummaries, getWindow, loadDemo, loadResults, showcaseId } from "@/lib/data";
import { cls, dur, fmt, okCount, parseAnswer, pct, tname } from "@/lib/format";
import { CHANNEL_SHORT, FARM, FARMS, GROUPS, SERIES } from "@/lib/labels";
import { defaultPins } from "@/lib/pins";
import { fmtDateTime, parseAnchor } from "@/lib/time";

export default function OverviewPage() {
  const { meta, windows } = loadDemo();
  const results = loadResults();
  const sums = allSummaries();
  const show = getWindow(showcaseId())!;
  const { body, ans } = parseAnswer(show.text);
  const pins = defaultPins(body).slice(0, 2);
  const series = pins.map((name, k) => { const m = meta.channels.find((c) => c.name === name)!; return { name, label: CHANNEL_SHORT[name] ?? m.label, unit: m.unit, values: show.channels[name], color: SERIES[k] }; });
  const event = show.gold === "none" || show.outcome.lead_time_min == null ? null : { leadMin: show.outcome.lead_time_min, message: show.outcome.message ?? cls(show.gold) };
  const head = results.runs.find((r) => r.headline);
  const hb = head?.splits.test_b;
  const pos = sums.filter((w) => w.gold !== "none").length;
  const classes = [...new Set(sums.map((w) => w.gold).filter((g) => g !== "none"))];
  const classRows = classes
    .map((c) => { const ws = sums.filter((w) => w.gold === c); return { c, n: ws.length, right: ws.filter((w) => w.pred === c).length, msgs: [...new Set(ws.map((w) => w.outcome.message).filter(Boolean))] as string[] }; })
    .sort((a, b) => b.n - a.n);
  const firstSentence = body.split(". ")[0] + ".";

  return (
    <div className="page">
      <section className={styles.hero} style={{ paddingTop: 26 }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 999, background: "var(--accent-soft)", color: "var(--accent-text)", fontSize: 12, fontWeight: 600, marginBottom: 12 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
            WIND FARM OPERATOR TERMINAL · TEMPORAL AI
          </div>
          <h1>Early warning for wind turbine fault stops & LCOE preservation</h1>
          <p className={styles.lead}>
            24 hours of multi-series SCADA in. Hours before the controller trips: predict forced outages, identify failing subsystems, quantify MWh & revenue at risk, and recommend prescriptive actions.
          </p>
          <div className={styles.cta}>
            <Link href="/window/" className="btn primary">Open Showcase Window <IconArrow /></Link>
            <Link href="/results/" className="btn">Evaluation & Benchmarks</Link>
          </div>
        </div>
        <div className="card">
          <div className="card-h">
            <div><h3>{tname(show)} · {fmtDateTime(parseAnchor(show.anchor))}</h3><span className="hint">asked {show.horizon_h} h ahead</span></div>
            <Link href={`/window/${show.id}/`} className="btn sm">Explore <IconArrow /></Link>
          </div>
          <div style={{ padding: "8px 10px 4px" }}>
            <SignalPanels anchor={show.anchor} series={series} horizonH={show.horizon_h} event={event} panelHeight={110} interactive={false} compact />
          </div>
        </div>
      </section>

      <div className="kpis">
        <div className="card kpi"><span className="v">{FARMS.length}</span><span className="l">wind farms</span><span className="c">Penmanshiel (train) · Kelmarsh (unseen site)</span></div>
        <div className="card kpi"><span className="v">{meta.channels.length}</span><span className="l">SCADA channels</span><span className="c">10-min RTDs, vibration, power curve</span></div>
        {hb && <div className="card kpi"><span className="v num">{fmt(hb.recall_at_10far, 2)}</span><span className="l">recall @ 10 % false alarms</span><span className="c">unseen farm (XGBoost baseline: 0.21)</span></div>}
        {head?.faithfulness && <div className="card kpi"><span className="v">{pct(head.faithfulness.claim_precision)}</span><span className="l">numbers that verify</span><span className="c">{head.faithfulness.claims.toLocaleString()} claims strictly verified</span></div>}
        <div className="card kpi"><span className="v">£2,500</span><span className="l">avoided O&M callout</span><span className="c">per proactive shift intervention</span></div>
      </div>

      <OperatorTriageQueue windows={sums} limit={6} />

      <FleetMap windows={sums} defaultFarm="kelmarsh" />

      <section className="section">
        <h2>How it works</h2>
        <div className={styles.steps}>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>1 · Input</span>
            <h3>24 hours of signals</h3>
            <p>144 samples × {meta.channels.length} channels. Nothing after &ldquo;now&rdquo;. The alarm log is never shown.</p>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>2 · Question</span>
            <h3>Fault stop within {show.horizon_h} h?</h3>
            <p>Asked 1, 3 or 6 h ahead. Name the subsystem. Reason first, decide last.</p>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>3 · Answer</span>
            <h3>Evidence, then one line</h3>
            <div className={styles.ex}>
              <Explanation body={firstSentence} claims={show.claims.filter((c) => c.end <= firstSentence.length)} />
              <div style={{ marginTop: 6 }}><code>{ans}</code></div>
            </div>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>4 · Checked</span>
            <h3>Numbers and outcome</h3>
            <div className={styles.ex}>
              <b>{okCount(show.claims)} of {show.claims.length}</b> numbers verified against the signals.<br />
              Log: <code>{show.outcome.message}</code> at +{dur(show.outcome.lead_time_min)}.
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>The data</h2>
        <div className={styles.two}>
          {FARMS.map((f) => {
            const ws = sums.filter((w) => w.farm === f);
            const turbines = [...new Set(ws.map((w) => w.turbine))].sort((a, b) => a - b);
            const months = ws.map((w) => w.anchor.slice(0, 7)).sort();
            return (
              <div key={f} className={`card ${styles.farm}`}>
                <h3>{FARM[f].name} <span className="chip accent">{FARM[f].tag}</span></h3>
                <p>{FARM[f].type} · {f === "kelmarsh" ? "never seen in training" : "trained on 2018–19, tested on 2020–21"}</p>
                <div className={styles.facts}>
                  <div><b>{turbines.length}</b><span>turbines</span></div>
                  <div><b>{ws.length}</b><span>windows</span></div>
                  <div><b className="num" style={{ fontSize: 15 }}>{months[0]} → {months[months.length - 1]}</b><span>window dates</span></div>
                </div>
                <div className={styles.tiles} aria-label="turbines">
                  {turbines.map((t) => <Link key={t} href={`/windows/?turbine=${f}|${t}`} className={`${styles.tile} ${styles.on}`}>T{String(t).padStart(2, "0")}</Link>)}
                </div>
                <Link href={`/farms/${f}/`} className="btn sm" style={{ alignSelf: "flex-start" }}>Farm board <IconArrow /></Link>
              </div>
            );
          })}
        </div>
      </section>

      <section className="section">
        <h2>The {meta.channels.length} signals</h2>
        <div className="card" style={{ padding: "4px 20px 8px" }}>
          <div className={styles.chan}>
            {GROUPS.map((g) => (
              <div key={g.title} className={styles.g}>
                <h4>{g.title}</h4>
                <div className={styles.sub}>{g.sub}</div>
                <ul>
                  {g.channels.map((name) => { const m = meta.channels.find((c) => c.name === name); return m ? <li key={name}><span>{CHANNEL_SHORT[name] ?? m.label}</span><span>{m.unit}</span></li> : null; })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <h2>The labels</h2>
        <p className="desc">Alarm-log messages → subsystem classes. Counted over the {windows.length} windows here.</p>
        <div className="card table-wrap">
          <table className="data">
            <thead><tr><th>Subsystem</th><th className="r">windows</th><th className="r">named correctly</th><th>messages in the log</th></tr></thead>
            <tbody>
              {classRows.map((r) => (
                <tr key={r.c}>
                  <td><span className="chip class">{cls(r.c)}</span></td>
                  <td className="r num">{r.n}</td>
                  <td className="r num">{r.right} / {r.n}</td>
                  <td style={{ whiteSpace: "normal" }}>{r.msgs.map((m) => <code key={m} className={styles.msg}>{m}</code>)}</td>
                </tr>
              ))}
              <tr><td><span className="chip neutral">no fault stop</span></td><td className="r num">{windows.length - pos}</td><td className="r num">{sums.filter((w) => w.gold === "none" && w.pred === "none").length} / {windows.length - pos}</td><td className="muted">quiet windows</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
