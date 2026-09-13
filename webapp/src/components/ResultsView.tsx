"use client";

import { useState } from "react";

import { cls, fmt, pct } from "@/lib/format";
import { SPLITS, SPLIT_NAME } from "@/lib/labels";
import type { ResultsSummary, RunSummary, Split } from "@/lib/types";

import styles from "./Results.module.css";

type Horizon = "all" | "1" | "3" | "6";
const HORIZONS: [Horizon, string][] = [["all", "pooled"], ["1", "1 h ahead"], ["3", "3 h ahead"], ["6", "6 h ahead"]];

export default function ResultsView({ results }: { results: ResultsSummary }) {
  const runs = results.runs;
  const head = runs.find((r) => r.headline) ?? runs[runs.length - 1];
  const base = runs.find((r) => r.run === "t1_flamingo_llama1b") ?? runs[0];
  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Results</h1>
          <p className="sub">
            Every model on the same held-out windows. Val: unseen turbines on the training farm. Test A: the training farm in years the model never saw.
            Test B: Kelmarsh, a farm and turbine type it never saw. Recall is measured at a 10 % false-alarm rate; subsystem accuracy is over the windows a
            fault stop actually followed.
          </p>
        </div>
      </div>
      <Tiles head={head} base={base} results={results} />
      <MainTable results={results} />
      <ClassRecall head={head} base={base} />
      <FaithTable runs={runs} />
      <ConfusionMatrix head={head} />
    </div>
  );
}

function Tiles({ head, base, results }: { head: RunSummary; base: RunSummary; results: ResultsSummary }) {
  const hb = head.splits.test_b, bb = base.splits.test_b;
  const xgb = results.baselines.find((b) => /sensor statistics/.test(b.label));
  const f = head.faithfulness;
  if (!hb || !bb) return null;
  return (
    <div className="kpis">
      <div className="card kpi"><span className="l">Recall at 10 % false alarms · unseen farm</span><span className="v num">{fmt(hb.recall_at_10far, 3)}</span><span className="c">headline model on {hb.n_pos} Kelmarsh stops · label-only Flamingo {fmt(bb.recall_at_10far, 3)}{xgb ? ` · XGBoost sensor statistics ${fmt(xgb.test_b.recall_at_10far, 3)}` : ""}</span></div>
      <div className="card kpi"><span className="l">Subsystem named correctly · unseen farm</span><span className="v num">{pct(hb.subsystem_acc)}</span><span className="c">over the {hb.n_pos} windows a fault stop followed · label-only Flamingo {pct(bb.subsystem_acc)}{hb.t3 ? ` · asked after the stop ${pct(hb.t3.subsystem_acc)}` : ""}</span></div>
      <div className="card kpi"><span className="l">Numbers in the explanation that verify</span><span className="v num">{f ? pct(f.claim_precision) : "–"}</span><span className="c">{f ? `${f.claims.toLocaleString()} numeric claims in ${f.n_texts.toLocaleString()} explanations, each recomputed from its window` : ""}</span></div>
      <div className="card kpi"><span className="l">Explanations with a wrong number</span><span className="v num">{f ? pct(f.texts_with_wrong_claim) : "–"}</span><span className="c">{f ? `conclusion agrees with the answer line in ${pct(f.conclusion_consistent)} of texts` : ""}</span></div>
    </div>
  );
}

function MainTable({ results }: { results: ResultsSummary }) {
  const [hz, setHz] = useState<Horizon>("all");
  const cellsFor = (r: RunSummary, s: Split) => {
    const sp = r.splits[s];
    if (!sp) return null;
    if (hz === "all") return { auroc: sp.auroc, recall: sp.recall_at_10far, f1: sp.hard_f1, acc: sp.subsystem_acc };
    const h = sp.horizons?.[hz];
    return h ? { auroc: h.auroc, recall: h.recall_at_10far, f1: h.hard_f1, acc: null } : null;
  };
  return (
    <section className="section">
      <h2>All models, all splits</h2>
      <div className="card">
        <div className="card-h">
          <div className={styles.ctl}>
            <span>Horizon</span>
            <div className="seg" role="group" aria-label="Horizon">{HORIZONS.map(([k, l]) => <button key={k} type="button" aria-pressed={hz === k} onClick={() => setHz(k)}>{l}</button>)}</div>
          </div>
          <span className="hint">{hz === "all" ? "all three horizons pooled" : `windows asked ${hz} h ahead · XGBoost rows and subsystem accuracy are pooled only`}</span>
        </div>
        <div className="table-wrap">
          <table className={`data ${styles.r}`}>
            <thead>
              <tr className={styles.top}><th>Model</th>{SPLITS.map((s) => <th key={s} colSpan={4} className={styles.gap}>{SPLIT_NAME[s]}</th>)}</tr>
              <tr><th />{SPLITS.map((s) => <Group key={s}><th className={`${styles.gap} ${styles.rr}`}>AUROC</th><th className={styles.rr}>recall @10 % FAR</th><th className={styles.rr}>hard F1</th><th className={styles.rr}>subsystem acc</th></Group>)}</tr>
            </thead>
            <tbody>
              {results.runs.map((r) => (
                <tr key={r.run} className={r.headline ? "headline" : undefined}>
                  <td>{r.label}{r.headline && <span className="chip accent" style={{ marginLeft: 8 }}>headline</span>}</td>
                  {SPLITS.map((s) => { const m = cellsFor(r, s); return <Group key={s}><td className={`${styles.gap} ${styles.rr}`}>{m ? fmt(m.auroc, 3) : "–"}</td><td className={styles.rr}>{m ? fmt(m.recall, 3) : "–"}</td><td className={styles.rr}>{m ? fmt(m.f1, 3) : "–"}</td><td className={styles.rr}>{m && m.acc != null ? fmt(m.acc, 2) : "–"}</td></Group>; })}
                </tr>
              ))}
              {results.baselines.map((b) => (
                <tr key={b.label}>
                  <td>{b.label}<span className="chip neutral" style={{ marginLeft: 8 }}>no explanation</span></td>
                  <td className={`${styles.gap} ${styles.rr}`}>–</td><td className={styles.rr}>–</td><td className={styles.rr}>–</td><td className={styles.rr}>–</td>
                  {(["test_a", "test_b"] as const).map((s) => <Group key={s}><td className={`${styles.gap} ${styles.rr}`}>{hz === "all" ? fmt(b[s].auroc, 3) : "–"}</td><td className={styles.rr}>{hz === "all" ? fmt(b[s].recall_at_10far, 3) : "–"}</td><td className={styles.rr}>–</td><td className={styles.rr}>–</td></Group>)}
                </tr>
              ))}
              <tr className="floor">
                <td>{results.floor.label}</td>
                {SPLITS.map((s) => <Group key={s}><td className={`${styles.gap} ${styles.rr}`}>{fmt(results.floor.auroc, 3)}</td><td className={styles.rr}>{fmt(results.floor.recall_at_10far, 3)}</td><td className={styles.rr}>–</td><td className={styles.rr}>–</td></Group>)}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p className={styles.note}>
        The headline model&apos;s AUROC uses its near-binary generate-mode score (the yes/no likelihood is conditioned on its own written conclusion), so its
        ranking metrics understate it; read its recall and F1 columns. Hard F1 is the written yes/no against what followed. XGBoost rows are the conventional
        baseline on 24 h summary statistics.
      </p>
    </section>
  );
}

function Group({ children }: { children: React.ReactNode }) { return <>{children}</>; }

function ClassRecall({ head, base }: { head: RunSummary; base: RunSummary }) {
  const [split, setSplit] = useState<Split>("test_b");
  const hp = head.splits[split]?.per_class ?? {};
  const bp = base.splits[split]?.per_class ?? {};
  const classes = Object.keys(hp).filter((c) => hp[c].n > 0).sort((a, b) => hp[b].n - hp[a].n);
  const SCALE = 80;
  return (
    <section className="section">
      <h2>Where the signal is: recall per subsystem</h2>
      <p className="desc">Grid, yaw and brake stops have no precursor at 10-minute resolution, and the model mostly stays quiet on them. Overspeed does; the thermal classes only partly. Bars are recall at 10 % false alarms; the count is how many such stops the split contains.</p>
      <div className="card">
        <div className="card-h">
          <div className={styles.ctl}><span>Split</span><div className="seg" role="group" aria-label="Split">{([["test_b", "Test B · Kelmarsh"], ["test_a", "Test A · Penmanshiel 2020–21"], ["val", "Val"]] as [Split, string][]).map(([k, l]) => <button key={k} type="button" aria-pressed={split === k} onClick={() => setSplit(k)}>{l}</button>)}</div></div>
          <p className="legend"><span><i style={{ background: "var(--line-2)" }} />label-only Flamingo</span><span><i style={{ background: "var(--accent)" }} />headline model</span></p>
        </div>
        <div className={styles.cls}>
          <span className={styles.h}>Subsystem</span><span className={styles.h} style={{ textAlign: "right" }}>stops</span><span className={`${styles.h} ${styles.p}`}>recall at 10 % false alarms</span>
          {classes.map((c) => { const hv = hp[c].recall_at_10far; const bv = bp[c]?.recall_at_10far ?? null; return (
            <Group key={c}>
              <span className={styles.name}>{cls(c)}</span>
              <span className={`${styles.n} num`}>{hp[c].n}</span>
              <span className={styles.pair}>
                <span className={`${styles.bar} ${styles.base}`}><i style={{ width: `${bv == null ? 0 : Math.round(bv * SCALE)}%` }} /><b>{fmt(bv, 2)}</b></span>
                <span className={`${styles.bar} ${styles.head}`}><i style={{ width: `${hv == null ? 0 : Math.round(hv * SCALE)}%` }} /><b>{fmt(hv, 2)}</b></span>
              </span>
            </Group>
          ); })}
        </div>
      </div>
    </section>
  );
}

function FaithTable({ runs }: { runs: RunSummary[] }) {
  const fr = runs.filter((r) => r.faithfulness);
  return (
    <section className="section">
      <h2>Is the explanation true?</h2>
      <p className="desc">Every number the model writes is recomputed from the window it was given. Claim precision is the share that match; &ldquo;texts with a wrong number&rdquo; is the share of explanations containing at least one that does not; the last column is how often the written conclusion agrees with the model&apos;s own answer line.</p>
      <div className="card table-wrap">
        <table className={`data ${styles.r}`}>
          <thead><tr><th>Model</th><th className={styles.rr}>texts</th><th className={styles.rr}>claims per text</th><th className={styles.rr}>claim precision</th><th className={styles.rr}>val</th><th className={styles.rr}>test A</th><th className={styles.rr}>test B</th><th className={styles.rr}>texts with a wrong number</th><th className={styles.rr}>conclusion = answer</th></tr></thead>
          <tbody>
            {fr.map((r) => { const f = r.faithfulness!; const ps = f.per_split ?? {}; return (
              <tr key={r.run} className={r.headline ? "headline" : undefined}>
                <td>{r.label}</td><td className={styles.rr}>{f.n_texts.toLocaleString()}</td><td className={styles.rr}>{fmt(f.claims_per_text, 1)}</td><td className={styles.rr}>{pct(f.claim_precision)}</td>
                <td className={styles.rr}>{pct(ps.val?.claim_precision)}</td><td className={styles.rr}>{pct(ps.test_a?.claim_precision)}</td><td className={styles.rr}>{pct(ps.test_b?.claim_precision)}</td>
                <td className={styles.rr}>{pct(f.texts_with_wrong_claim)}</td><td className={styles.rr}>{pct(f.conclusion_consistent)}</td>
              </tr>
            ); })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ConfusionMatrix({ head }: { head: RunSummary }) {
  const cm = head.splits.test_b?.confusion;
  if (!cm) return null;
  const short = (c: string) => cls(c).replace(" / ", "/");
  const max = Math.max(...cm.data.flat());
  return (
    <section className="section">
      <details className={`card ${styles.more}`}>
        <summary>Confusion matrix of the headline model on Kelmarsh (rows: what followed, columns: what the model answered)</summary>
        <div className="table-wrap" style={{ padding: "0 18px 16px" }}>
          <table className={styles.cm}>
            <thead><tr><th className={styles.rh}>followed ↓ · answered →</th>{cm.columns.map((c) => <th key={c}>{short(c)}</th>)}<th>n</th></tr></thead>
            <tbody>
              {cm.index.map((r, i) => { const tot = cm.data[i].reduce((a, b) => a + b, 0); return (
                <tr key={r}><th className={styles.rh}>{short(r)}</th>{cm.data[i].map((v, j) => <td key={j} className={i === j ? styles.d : undefined} style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(Math.sqrt(v / max) * 55)}%, transparent)` }}>{v}</td>)}<td className="muted">{tot}</td></tr>
              ); })}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
