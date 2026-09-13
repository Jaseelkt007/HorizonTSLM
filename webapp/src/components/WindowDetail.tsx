"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { cls, dur, fmt, okCount, parseAnswer, pct, stateLabel, tname } from "@/lib/format";
import { FARM } from "@/lib/labels";
import type { ChannelMeta, Question, WindowRecord } from "@/lib/types";

import ChannelWall from "./ChannelWall";
import Explanation from "./Explanation";
import { VerdictChip } from "./Icons";
import Timeline from "./Timeline";
import styles from "./Window.module.css";

/** One held-out window: the question, the model's answer with verified numbers, what followed, and the signals. */
export default function WindowDetail({ w, meta }: { w: WindowRecord; meta: ChannelMeta[] }) {
  const params = useSearchParams();
  const hasT3 = !!w.t3_text;
  const [q, setQ] = useState<Question>(params.get("q") === "t3" && hasT3 ? "t3" : "t1");
  const choose = (next: Question) => {
    setQ(next);
    const url = new URL(window.location.href);
    if (next === "t3") url.searchParams.set("q", "t3"); else url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
  };

  const text = q === "t1" ? w.text : (w.t3_text ?? "");
  const claims = (q === "t1" ? w.claims : w.t3_claims) ?? [];
  const { body, ans, label } = parseAnswer(text);
  const nOk = okCount(claims);
  const right = label === w.gold;
  const o = w.outcome;
  const probs = Object.entries(w.class_scores ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <div className={styles.case}>
        <h2>
          {tname(w)} <span className="muted" style={{ fontWeight: 500 }}>· {FARM[w.farm].type}</span>
        </h2>
        <div className={styles.meta}>
          <span>Window ending <b className="num">{w.anchor}</b></span>
          <span className="chip accent">{FARM[w.farm].tag}</span>
          <span className="chip neutral">{stateLabel(w.state)}</span>
          <span className="chip neutral">asked {w.horizon_h} h ahead</span>
        </div>
      </div>

      <div className={styles.ask}>
        <div className="seg" role="group" aria-label="Question">
          <button type="button" aria-pressed={q === "t1"} onClick={() => choose("t1")}>Before the stop</button>
          <button type="button" aria-pressed={q === "t3"} disabled={!hasT3} onClick={() => choose("t3")} title={hasT3 ? undefined : "Only windows ending one hour before a stop were asked the post-hoc question"}>
            After the stop
          </button>
        </div>
        <p className={styles.q}>
          {q === "t1" ? (
            <>
              <b>Before the stop.</b> The model sees the 24 h ending {w.anchor} and the prompt: the turbine is currently{" "}
              {w.state === "producing" ? "producing" : "idle in low wind"}; will a fault-related stop begin within the next <b>{w.horizon_h} hours</b>, and if so
              in which subsystem?
            </>
          ) : (
            <>
              <b>After the stop.</b> The same 24 h, and the prompt: a status event began about one hour after the end of this window and stopped the
              turbine; describe what the signals show and name the subsystem.
            </>
          )}
        </p>
      </div>

      <div className={`panel ${styles.assess}`}>
        <div className={styles.main}>
          <div className="eyebrow">The model&apos;s answer</div>
          <Explanation body={body} claims={claims} className={styles.prose} />
          <div className={styles.ans}>
            <code>{ans}</code>
            {label && <span className={`chip ${label === "none" ? "neutral" : "class"}`}>{cls(label)}</span>}
            <VerdictChip right={right} long />
          </div>
          <div className={styles.tally}>
            <span><b>{nOk} of {claims.length}</b> numbers verified against the window</span>
            <span className="legend">
              <span><i style={{ background: "var(--good)" }} />verified</span>
              <span><i style={{ background: "var(--crit)" }} />does not match</span>
            </span>
          </div>
        </div>
        <div className={styles.side}>
          {q === "t1" ? (
            <>
              <div>
                <h4>P(fault stop within {w.horizon_h} h)</h4>
                <div className={`${styles.big} num`}>{fmt(w.score, 2)}</div>
                <div className="meter" style={{ marginTop: 8 }} role="img" aria-label={pct(w.score)}>
                  <i style={{ width: `${Math.round(w.score * 100)}%` }} />
                </div>
                <p className={styles.note} style={{ marginTop: 6 }}>Yes-versus-no likelihood after the model&apos;s own reasoning; it is near-binary by construction.</p>
              </div>
              <div>
                <h4>Subsystem probabilities</h4>
                <div className={styles.probs}>
                  {probs.map(([c, p]) => (
                    <FragmentRow key={c} name={cls(c)} gold={c === w.gold} p={p} />
                  ))}
                </div>
                {w.gold !== "none" && <p className={styles.note} style={{ marginTop: 6 }}>Bold = the subsystem that actually stopped.</p>}
              </div>
            </>
          ) : (
            <>
              <div>
                <h4>Model&apos;s subsystem</h4>
                <div className={styles.big}>{cls(label || "?")}</div>
              </div>
              <div>
                <h4>Alarm log</h4>
                <div style={{ fontWeight: 600 }}>{cls(w.gold)}</div>
                <p className={styles.note} style={{ marginTop: 4 }}>{o.message ?? ""}</p>
              </div>
            </>
          )}
        </div>
      </div>

      <div className={`panel ${styles.outcome}`}>
        <div>
          <div className="eyebrow">What actually happened</div>
          <p>
            {w.gold === "none" ? (
              <>No fault-class stop began in the next {w.horizon_h} h. The right answer was <span className={styles.msg}>Answer: no</span>.</>
            ) : (
              <>
                The controller logged <span className={styles.msg}>{o.message ?? ""}</span> <b>{dur(o.lead_time_min)}</b> after the end of this window
                {o.duration_h != null && <>, stopping the turbine for {o.duration_h < 1 ? `${Math.round(o.duration_h * 60)} min` : `${fmt(o.duration_h, 1)} h`}</>}.
                Subsystem: <b>{cls(w.gold)}</b>.
              </>
            )}
          </p>
        </div>
        <div className={styles.tl}><Timeline w={w} /></div>
      </div>

      <div className={styles.wallhead}>
        <h3>The 24 hours the model saw</h3>
        <span className="legend">
          <span><i style={{ background: "var(--band)" }} />last hour</span>
          <span><i style={{ background: "var(--accent)" }} />channel the explanation cites</span>
          <span><i style={{ background: "var(--series)" }} />other channels</span>
        </span>
      </div>
      <ChannelWall channels={w.channels} meta={meta} body={body} />
    </>
  );
}

function FragmentRow({ name, gold, p }: { name: string; gold: boolean; p: number }) {
  return (
    <>
      <span className={`${styles.l} ${gold ? styles.gold : ""}`}>{name}</span>
      <span className={styles.bar}><i style={{ width: `${Math.round(p * 100)}%` }} /></span>
      <span className={`${styles.n} num`}>{fmt(p, 2)}</span>
    </>
  );
}
