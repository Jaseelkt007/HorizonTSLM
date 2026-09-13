import Link from "next/link";

import Explanation from "@/components/Explanation";
import { IconArrow } from "@/components/Icons";
import styles from "@/components/Overview.module.css";
import SignalPanels from "@/components/SignalPanels";
import { allSummaries, getWindow, loadDemo, loadResults, showcaseId } from "@/lib/data";
import { cls, dur, okCount, parseAnswer, pct, tname } from "@/lib/format";
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
  const pos = sums.filter((w) => w.gold !== "none").length;
  const classes = [...new Set(sums.map((w) => w.gold).filter((g) => g !== "none"))];
  const classRows = classes
    .map((c) => { const ws = sums.filter((w) => w.gold === c); return { c, n: ws.length, right: ws.filter((w) => w.pred === c).length, msgs: [...new Set(ws.map((w) => w.outcome.message).filter(Boolean))] as string[] }; })
    .sort((a, b) => b.n - a.n);
  const monthOf = (a: string) => a.slice(0, 7);

  return (
    <div className="page">
      <section className={styles.hero} style={{ paddingTop: 26 }}>
        <div>
          <h1>Early warning for wind-turbine fault stops, with evidence you can check</h1>
          <p className={styles.lead}>
            A time-series language model reads the last 24 hours of a turbine&apos;s SCADA signals and says whether a fault stop is coming, in which subsystem,
            and why — hours before the controller trips. Every number in its explanation is recomputed from the signals it saw, and every answer here is
            scored against what the alarm log actually recorded afterwards.
          </p>
          <div className={styles.cta}>
            <Link href="/window/" className="btn primary">Open a window <IconArrow /></Link>
            <Link href="/results/" className="btn">See the results</Link>
          </div>
        </div>
        <div className="card">
          <div className="card-h">
            <div><h3>{tname(show)} · {fmtDateTime(parseAnchor(show.anchor))}</h3><span className="hint">two of the 19 channels, then the {show.horizon_h} h horizon the model was asked about</span></div>
            <Link href={`/window/${show.id}/`} className="btn sm">Explore <IconArrow /></Link>
          </div>
          <div style={{ padding: "8px 10px 4px" }}>
            <SignalPanels anchor={show.anchor} series={series} horizonH={show.horizon_h} event={event} panelHeight={110} interactive={false} compact />
          </div>
        </div>
      </section>

      <div className="kpis">
        <div className="card kpi"><span className="v">{FARMS.length}</span><span className="l">wind farms</span><span className="c">Kelmarsh (Senvion MM92) and Penmanshiel (MM82)</span></div>
        <div className="card kpi"><span className="v">{meta.channels.length}</span><span className="l">SCADA channels</span><span className="c">10-minute means, 144 samples per window</span></div>
        <div className="card kpi"><span className="v">{windows.length}</span><span className="l">held-out windows</span><span className="c">{pos} followed by a fault stop, {windows.length - pos} quiet</span></div>
        <div className="card kpi"><span className="v">{results.runs.length}</span><span className="l">models compared</span><span className="c">plus {results.baselines.length} XGBoost baselines on the same splits</span></div>
        {head?.faithfulness && <div className="card kpi"><span className="v">{pct(head.faithfulness.claim_precision)}</span><span className="l">numbers that verify</span><span className="c">{head.faithfulness.claims.toLocaleString()} numeric claims checked</span></div>}
      </div>

      <section className="section">
        <h2>How it works</h2>
        <div className={styles.steps}>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>1 · Input</span>
            <h3>24 hours of signals</h3>
            <p>144 ten-minute samples of {meta.channels.length} channels — wind, power, rotor, pitch, temperatures, oil pressure, tower vibration, grid, yaw — ending &ldquo;now&rdquo;. Nothing after that instant is an input.</p>
            <div className={styles.ex}>The turbine&apos;s name, type, the month and whether it is producing are the only context. The alarm log is never shown to the model.</div>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>2 · Question</span>
            <h3>Will a fault stop begin within the next {show.horizon_h} hours?</h3>
            <p>Asked 1, 3 or 6 hours ahead. If yes, the model must name the subsystem from a fixed list, and it must reason before it answers.</p>
            <div className={styles.ex}>&ldquo;Analyse the signals and decide whether a fault-related stop is likely to begin within the next {show.horizon_h} hours. Do not state a decision until the final line. End with <code>Answer:</code>&rdquo;</div>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>3 · Answer</span>
            <h3>Evidence first, then the label</h3>
            <p>A short explanation in plain language, then one parseable line that is scored.</p>
            <div className={styles.ex}>
              <Explanation body={body.split(". ").slice(0, 2).join(". ") + "…"} claims={show.claims.filter((c) => c.end <= body.split(". ").slice(0, 2).join(". ").length)} />
              <div style={{ marginTop: 6 }}><code>{ans}</code></div>
            </div>
          </div>
          <div className={`card ${styles.step}`}>
            <span className={styles.n}>4 · Checked</span>
            <h3>Against the signals and the log</h3>
            <p>Every number in the text is recomputed from the window; the answer line is compared with the alarm the controller logged afterwards.</p>
            <div className={styles.ex}>
              <b>{okCount(show.claims)} of {show.claims.length}</b> numbers verified. The log: <code>{show.outcome.message}</code> {dur(show.outcome.lead_time_min)} after the end of the window — the answer was right.
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>The data</h2>
        <p className="desc">Cubico&apos;s open SCADA exports for two UK wind farms (Zenodo, CC-BY-4.0): ten-minute telemetry plus the controller&apos;s status log. The model is trained on Penmanshiel 2018–19 and tested where it hurts: the same farm in later years, and a different farm with a different turbine type.</p>
        <div className={styles.two}>
          {FARMS.map((f) => {
            const ws = sums.filter((w) => w.farm === f);
            const turbines = [...new Set(ws.map((w) => w.turbine))].sort((a, b) => a - b);
            const months = ws.map((w) => monthOf(w.anchor)).sort();
            return (
              <div key={f} className={`card ${styles.farm}`}>
                <h3>{FARM[f].name} <span className="chip accent">{FARM[f].tag}</span></h3>
                <p>{FARM[f].type}. {FARM[f].why[0].toUpperCase() + FARM[f].why.slice(1)}.</p>
                <div className={styles.facts}>
                  <div><b>{turbines.length}</b><span>turbines sampled</span></div>
                  <div><b>{ws.length}</b><span>windows</span></div>
                  <div><b className="num" style={{ fontSize: 15 }}>{months[0]} → {months[months.length - 1]}</b><span>sampled window dates</span></div>
                </div>
                <div className={styles.tiles} aria-label="turbines">
                  {turbines.map((t) => (
                    <Link key={t} href={`/windows/?turbine=${f}|${t}`} className={`${styles.tile} ${styles.on}`}>T{String(t).padStart(2, "0")}</Link>
                  ))}
                </div>
                <Link href={`/farms/${f}/`} className="btn sm" style={{ alignSelf: "flex-start" }}>Farm board <IconArrow /></Link>
              </div>
            );
          })}
        </div>
      </section>

      <section className="section">
        <h2>The {meta.channels.length} signals the model reads</h2>
        <p className="desc">Grouped by the subsystem they tell you about. Two are derived from the others (the power-curve residual and the yaw misalignment); the rest are the raw ten-minute means from the SCADA export.</p>
        <div className="card" style={{ padding: "4px 20px 8px" }}>
          <div className={styles.chan}>
            {GROUPS.map((g) => (
              <div key={g.title} className={styles.g}>
                <h4>{g.title}</h4>
                <div className={styles.sub}>{g.sub}</div>
                <ul>
                  {g.channels.map((name) => { const m = meta.channels.find((c) => c.name === name); return m ? <li key={name}><span>{m.label}</span><span>{m.unit}</span></li> : null; })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <h2>The alarm log becomes the labels</h2>
        <p className="desc">The controller&apos;s status messages are mapped to subsystem classes. A window is positive when a fault-class stop began within the asked horizon after it — the message itself is never an input. Counts below are for the {windows.length} windows on this site.</p>
        <div className="card table-wrap">
          <table className="data">
            <thead><tr><th>Subsystem</th><th className="r">windows</th><th className="r">named correctly</th><th>messages seen in the log</th></tr></thead>
            <tbody>
              {classRows.map((r) => (
                <tr key={r.c}>
                  <td><span className="chip class">{cls(r.c)}</span></td>
                  <td className="r num">{r.n}</td>
                  <td className="r num">{r.right} / {r.n}</td>
                  <td style={{ whiteSpace: "normal" }}>{r.msgs.map((m) => <code key={m} className={styles.msg}>{m}</code>)}</td>
                </tr>
              ))}
              <tr><td><span className="chip neutral">no fault stop</span></td><td className="r num">{windows.length - pos}</td><td className="r num">{sums.filter((w) => w.gold === "none" && w.pred === "none").length} / {windows.length - pos}</td><td className="muted">quiet windows — the right answer is &ldquo;no&rdquo;</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
