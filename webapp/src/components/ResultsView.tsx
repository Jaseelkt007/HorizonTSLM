"use client";

import { useState } from "react";

import { cls, fmt, pct } from "@/lib/format";
import { SPLITS, SPLIT_NAME } from "@/lib/labels";
import type { ResultsSummary, RunSummary, Split } from "@/lib/types";

import styles from "./Results.module.css";

type Horizon = "all" | "1" | "3" | "6";
const HORIZONS: [Horizon, string][] = [["all", "pooled"], ["1", "1 h ahead"], ["3", "3 h ahead"], ["6", "6 h ahead"]];
const HZ_NOTE: Record<Horizon, string> = {
  all: "all three horizons pooled",
  "1": "windows asked 1 h ahead · XGBoost rows and subsystem accuracy are reported pooled only",
  "3": "windows asked 3 h ahead · XGBoost rows and subsystem accuracy are reported pooled only",
  "6": "windows asked 6 h ahead · XGBoost rows and subsystem accuracy are reported pooled only",
};

export default function ResultsView({ results }: { results: ResultsSummary }) {
  const runs = results.runs;
  const head = runs.find((r) => r.headline) ?? runs[runs.length - 1];
  const base = runs.find((r) => r.run === "t1_flamingo_llama1b") ?? runs[0];
  return (
    <section className={`view ${styles.results}`} aria-label="Results">
      <div className={styles.sec}>
        <h2>Every model on the same held-out windows</h2>
        <p>
          Val: unseen turbines on the training farm. Test A: the training farm in years the model never saw. Test B: Kelmarsh, a farm and turbine type it
          never saw. Recall is measured at a 10 % false-alarm rate; subsystem accuracy is over the windows a fault stop actually followed. The XGBoost rows
          are the conventional baseline on 24 h summary statistics and give no explanation.
        </p>
        <Tiles head={head} base={base} results={results} />
      </div>
      <MainTable results={results} />
      <ClassRecall head={head} base={base} />
      <FaithTable runs={runs} />
      <ConfusionMatrix head={head} />
    </section>
  );
}

function Tiles({ head, base, results }: { head: RunSummary; base: RunSummary; results: ResultsSummary }) {
  const hb = head.splits.test_b;
  const bb = base.splits.test_b;
  const xgb = results.baselines.find((b) => /sensor statistics/.test(b.label));
  const f = head.faithfulness;
  if (!hb || !bb) return null;
  const tiles = [
    {
      l: "Recall at 10 % false alarms, unseen farm",
      v: fmt(hb.recall_at_10far, 3),
      c: `headline model on ${hb.n_pos} Kelmarsh stops · label-only Flamingo ${fmt(bb.recall_at_10far, 3)}${xgb ? ` · XGBoost sensor statistics ${fmt(xgb.test_b.recall_at_10far, 3)}` : ""}`,
    },
    {
      l: "Subsystem named correctly, unseen farm",
      v: pct(hb.subsystem_acc),
      c: `over the ${hb.n_pos} windows a fault stop followed · label-only Flamingo ${pct(bb.subsystem_acc)}${hb.t3 ? ` · asked after the stop ${pct(hb.t3.subsystem_acc)}` : ""}`,
    },
    {
      l: "Numbers in the explanation that verify",
      v: f ? pct(f.claim_precision) : "–",
      c: f ? `${f.claims.toLocaleString()} numeric claims in ${f.n_texts.toLocaleString()} explanations, each recomputed from its window` : "",
    },
    {
      l: "Explanations with at least one wrong number",
      v: f ? pct(f.texts_with_wrong_claim) : "–",
      c: f ? `conclusion agrees with the answer line in ${pct(f.conclusion_consistent)} of texts` : "",
    },
  ];
  return (
    <div className={styles.tiles}>
      {tiles.map((t) => (
        <div key={t.l} className={`panel ${styles.tile}`}>
          <span className={styles.l}>{t.l}</span>
          <span className={styles.v}>{t.v}</span>
          <span className={styles.c}>{t.c}</span>
        </div>
      ))}
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
    <div className={styles.sec}>
      <div className={styles.ctl}>
        <span>Horizon</span>
        <div className="seg" role="group" aria-label="Horizon">
          {HORIZONS.map(([k, l]) => (
            <button key={k} type="button" aria-pressed={hz === k} onClick={() => setHz(k)}>{l}</button>
          ))}
        </div>
        <span className="muted">{HZ_NOTE[hz]}</span>
      </div>
      <div className={`panel ${styles.twrap}`}>
        <table className={styles.r}>
          <thead>
            <tr>
              <th>Model</th>
              {SPLITS.map((s) => <th key={s} colSpan={4} className={styles.gap}>{SPLIT_NAME[s]}</th>)}
            </tr>
            <tr>
              <th />
              {SPLITS.map((s) => (
                <Fragment4 key={s}>
                  <th className={styles.gap}>AUROC</th><th>recall @10 % FAR</th><th>hard F1</th><th>subsystem acc</th>
                </Fragment4>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.runs.map((r) => (
              <tr key={r.run} className={r.headline ? styles.headline : undefined}>
                <td>{r.label}{r.headline && <span className={`chip accent ${styles.chipgap}`}>headline</span>}</td>
                {SPLITS.map((s) => {
                  const m = cellsFor(r, s);
                  return (
                    <Fragment4 key={s}>
                      <td className={styles.gap}>{m ? fmt(m.auroc, 3) : "–"}</td>
                      <td>{m ? fmt(m.recall, 3) : "–"}</td>
                      <td>{m ? fmt(m.f1, 3) : "–"}</td>
                      <td>{m && m.acc != null ? fmt(m.acc, 2) : "–"}</td>
                    </Fragment4>
                  );
                })}
              </tr>
            ))}
            {results.baselines.map((b) => (
              <tr key={b.label}>
                <td>{b.label}<span className={`chip neutral ${styles.chipgap}`}>no explanation</span></td>
                <td className={styles.gap}>–</td><td>–</td><td>–</td><td>–</td>
                {(["test_a", "test_b"] as const).map((s) => (
                  <Fragment4 key={s}>
                    <td className={styles.gap}>{hz === "all" ? fmt(b[s].auroc, 3) : "–"}</td>
                    <td>{hz === "all" ? fmt(b[s].recall_at_10far, 3) : "–"}</td>
                    <td>–</td><td>–</td>
                  </Fragment4>
                ))}
              </tr>
            ))}
            <tr className={styles.floor}>
              <td>{results.floor.label}</td>
              {SPLITS.map((s) => (
                <Fragment4 key={s}>
                  <td className={styles.gap}>{fmt(results.floor.auroc, 3)}</td><td>{fmt(results.floor.recall_at_10far, 3)}</td><td>–</td><td>–</td>
                </Fragment4>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className={styles.note}>
        Headline-model AUROC uses its near-binary generate-mode score (the yes/no likelihood is conditioned on the model&apos;s own written conclusion), so its
        ranking metrics understate it; read its recall and F1 columns. Hard F1 is the written yes/no against what followed.
      </p>
    </div>
  );
}

// React fragments with keys, for the grouped table cells.
function Fragment4({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function ClassRecall({ head, base }: { head: RunSummary; base: RunSummary }) {
  const [split, setSplit] = useState<Split>("test_b");
  const hp = head.splits[split]?.per_class ?? {};
  const bp = base.splits[split]?.per_class ?? {};
  const classes = Object.keys(hp).filter((c) => hp[c].n > 0).sort((a, b) => hp[b].n - hp[a].n);
  const SCALE = 82; // % of the column a recall of 1.0 fills, leaving room for the trailing label
  return (
    <div className={styles.sec}>
      <h2>Where the signal is: recall per subsystem</h2>
      <p>
        Grid, yaw and brake stops have no precursor at 10-minute resolution, and the model mostly stays quiet on them. Overspeed does, and the thermal
        classes only partly. Bars are recall at 10 % false alarms; the count is how many such stops the split contains.
      </p>
      <div className={styles.ctl}>
        <span>Split</span>
        <div className="seg" role="group" aria-label="Split">
          {([["test_b", "Test B · Kelmarsh"], ["test_a", "Test A · Penmanshiel 2020–21"], ["val", "Val"]] as [Split, string][]).map(([k, l]) => (
            <button key={k} type="button" aria-pressed={split === k} onClick={() => setSplit(k)}>{l}</button>
          ))}
        </div>
      </div>
      <div className={`panel ${styles.cls}`}>
        <span className={styles.h}>Subsystem</span>
        <span className={styles.h} style={{ textAlign: "right" }}>stops</span>
        <span className={`${styles.h} ${styles.p}`}>recall at 10 % false alarms</span>
        {classes.map((c) => {
          const hv = hp[c].recall_at_10far;
          const bv = bp[c]?.recall_at_10far ?? null;
          return (
            <FragmentRow key={c}>
              <span className={styles.name}>{cls(c)}</span>
              <span className={`${styles.n} num`}>{hp[c].n}</span>
              <span className={styles.pair}>
                <span className={`${styles.bar} ${styles.base}`}><i style={{ width: `${bv == null ? 0 : Math.round(bv * SCALE)}%` }} /><b>{fmt(bv, 2)}</b></span>
                <span className={`${styles.bar} ${styles.head}`}><i style={{ width: `${hv == null ? 0 : Math.round(hv * SCALE)}%` }} /><b>{fmt(hv, 2)}</b></span>
              </span>
            </FragmentRow>
          );
        })}
      </div>
      <p className="legend">
        <span><i style={{ background: "var(--line-strong)" }} />label-only Flamingo</span>
        <span><i style={{ background: "var(--accent)" }} />headline model (reason-first + rich channel text)</span>
      </p>
    </div>
  );
}

function FragmentRow({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function FaithTable({ runs }: { runs: RunSummary[] }) {
  const fr = runs.filter((r) => r.faithfulness);
  return (
    <div className={styles.sec}>
      <h2>Is the explanation true?</h2>
      <p>
        Every number the model writes is recomputed from the window it was given. Claim precision is the share that match; &ldquo;texts with a wrong
        number&rdquo; is the share of explanations containing at least one that does not; the last column is how often the written conclusion agrees with
        the model&apos;s own answer line.
      </p>
      <div className={`panel ${styles.twrap}`}>
        <table className={styles.r}>
          <thead>
            <tr>
              <th>Model</th><th>texts</th><th>claims per text</th><th>claim precision</th><th>val</th><th>test A</th><th>test B</th><th>texts with a wrong number</th><th>conclusion = answer</th>
            </tr>
          </thead>
          <tbody>
            {fr.map((r) => {
              const f = r.faithfulness!;
              const ps = f.per_split ?? {};
              return (
                <tr key={r.run} className={r.headline ? styles.headline : undefined}>
                  <td>{r.label}</td>
                  <td>{f.n_texts.toLocaleString()}</td>
                  <td>{fmt(f.claims_per_text, 1)}</td>
                  <td>{pct(f.claim_precision)}</td>
                  <td>{pct(ps.val?.claim_precision)}</td>
                  <td>{pct(ps.test_a?.claim_precision)}</td>
                  <td>{pct(ps.test_b?.claim_precision)}</td>
                  <td>{pct(f.texts_with_wrong_claim)}</td>
                  <td>{pct(f.conclusion_consistent)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConfusionMatrix({ head }: { head: RunSummary }) {
  const cm = head.splits.test_b?.confusion;
  if (!cm) return null;
  const short = (c: string) => cls(c).replace(" / ", "/");
  const max = Math.max(...cm.data.flat());
  return (
    <div className={styles.sec}>
      <details className={styles.more}>
        <summary>Confusion matrix of the headline model on Kelmarsh (rows: what followed, columns: what the model answered)</summary>
        <div className={`panel ${styles.twrap}`}>
          <table className={styles.cm}>
            <thead>
              <tr>
                <th className={styles.rh}>followed ↓ · answered →</th>
                {cm.columns.map((c) => <th key={c}>{short(c)}</th>)}
                <th>n</th>
              </tr>
            </thead>
            <tbody>
              {cm.index.map((r, i) => {
                const tot = cm.data[i].reduce((a, b) => a + b, 0);
                return (
                  <tr key={r}>
                    <th className={styles.rh}>{short(r)}</th>
                    {cm.data[i].map((v, j) => (
                      <td key={j} className={i === j ? styles.d : undefined} style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(Math.sqrt(v / max) * 55)}%, transparent)` }}>
                        {v}
                      </td>
                    ))}
                    <td className="muted">{tot}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
