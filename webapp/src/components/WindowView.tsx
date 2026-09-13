"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { cls, dur, fmt, okCount, parseAnswer, pct, stateLabel, tname } from "@/lib/format";
import { CHANNEL_SHORT, FARM, MAX_PINNED, SERIES } from "@/lib/labels";
import { citedChannels, defaultPins } from "@/lib/pins";
import { fmtDateTime, parseAnchor } from "@/lib/time";
import type { ChannelMeta, Question, WindowRecord } from "@/lib/types";

import ChannelList from "./ChannelList";
import Explanation from "./Explanation";
import { IconArrow, VerdictChip } from "./Icons";
import SignalPanels from "./SignalPanels";
import styles from "./Window.module.css";

interface Props { w: WindowRecord; meta: ChannelMeta[]; prev?: string; next?: string }

export default function WindowView({ w, meta, prev, next }: Props) {
  const params = useSearchParams();
  const hasT3 = !!w.t3_text;
  const [q, setQ] = useState<Question>(params.get("q") === "t3" && hasT3 ? "t3" : "t1");
  const text = q === "t1" ? w.text : (w.t3_text ?? "");
  const claims = (q === "t1" ? w.claims : w.t3_claims) ?? [];
  const { body, ans, label } = parseAnswer(text);
  const cited = new Set(citedChannels(body));
  const [pinned, setPinned] = useState<string[]>(() => defaultPins(parseAnswer(w.text).body));
  const toggle = (name: string) =>
    setPinned((p) => (p.includes(name) ? (p.length > 1 ? p.filter((x) => x !== name) : p) : p.length >= MAX_PINNED ? [...p.slice(1), name] : [...p, name]));
  const choose = (nq: Question) => {
    setQ(nq);
    const url = new URL(window.location.href);
    if (nq === "t3") url.searchParams.set("q", "t3"); else url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
  };

  const o = w.outcome;
  const right = label === w.gold;
  const nOk = okCount(claims);
  const probs = Object.entries(w.class_scores ?? {}).sort((a, b) => b[1] - a[1]);
  const series = pinned.map((name, k) => {
    const m = meta.find((c) => c.name === name)!;
    return { name, label: CHANNEL_SHORT[name] ?? m.label, unit: m.unit, values: w.channels[name], color: SERIES[k] };
  });
  const event = w.gold === "none" || o.lead_time_min == null ? null : { leadMin: o.lead_time_min, message: o.message ?? cls(w.gold) };

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <div className="crumbs"><Link href="/windows/">Windows</Link><span>/</span><Link href={`/farms/${w.farm}/`}>{FARM[w.farm].name}</Link><span>/</span><span>{tname(w)}</span></div>
          <h1>{tname(w)} · window ending {fmtDateTime(parseAnchor(w.anchor))}</h1>
          <p className="sub">{FARM[w.farm].type} · <span className="chip accent">{FARM[w.farm].tag}</span> · {stateLabel(w.state)} · asked {w.horizon_h} h ahead</p>
        </div>
        <div className="actions">
          <div className="seg" role="group" aria-label="Question">
            <button type="button" aria-pressed={q === "t1"} onClick={() => choose("t1")}>Before the stop</button>
            <button type="button" aria-pressed={q === "t3"} disabled={!hasT3} onClick={() => choose("t3")} title={hasT3 ? undefined : "Only windows ending one hour before a stop were asked the post-hoc question"}>After the stop</button>
          </div>
          {prev ? <Link className="btn sm" href={`/window/${prev}/`}>← earlier</Link> : <span className="btn sm" aria-disabled="true" style={{ opacity: 0.45 }}>← earlier</span>}
          {next ? <Link className="btn sm" href={`/window/${next}/`}>later →</Link> : <span className="btn sm" aria-disabled="true" style={{ opacity: 0.45 }}>later →</span>}
        </div>
      </div>

      <div className={`${styles.grid} ${styles.stretch}`}>
        <div className="card">
          <div className="card-h">
            <div><h3>What the model saw</h3><span className="hint">24 h · 10-minute means · nothing after &ldquo;now&rdquo; is an input</span></div>
            <p className="legend">
              <span><i style={{ background: "var(--band)" }} />last hour</span>
              <span><i style={{ background: "var(--future)", border: "1px solid var(--accent-line)" }} />asked horizon</span>
              {event && <span><i className="line" style={{ background: "var(--crit)" }} />stop began</span>}
            </p>
          </div>
          <div className="card-b" style={{ padding: "12px 12px 8px" }}>
            <SignalPanels anchor={w.anchor} series={series} horizonH={w.horizon_h} event={event} panelHeight={165} />
          </div>
        </div>
        <div className={`card ${styles.chanCard}`}>
          <div className="card-h"><h3>Channels</h3><span className="hint">click to chart</span></div>
          <ChannelList meta={meta} channels={w.channels} cited={cited} pinned={pinned} onToggle={toggle} />
        </div>
      </div>

      <div className={styles.grid}>
        <div className="card">
          <div className="card-h"><h3>The model&apos;s answer</h3><span className="hint">{q === "t1" ? "asked before the stop" : "asked after the stop"}</span></div>
          <p className={styles.q}>
            {q === "t1" ? (
              <><b>Asked:</b> will a fault stop begin within the next <b>{w.horizon_h} h</b>? Which subsystem?</>
            ) : (
              <><b>Asked:</b> a stop began about one hour after this window. What do the signals show? Which subsystem?</>
            )}
          </p>
          <div className="card-b">
            <Explanation body={body} claims={claims} className={styles.prose} />
            <div className={styles.ans}>
              <code>{ans}</code>
              {label && <span className={`chip ${label === "none" ? "neutral" : "class"}`}>{cls(label)}</span>}
              <VerdictChip right={right} long />
            </div>
            <div className={styles.tally}>
              <span><b>{nOk} of {claims.length}</b> numbers verified</span>
              <span className="legend">
                <span><i style={{ background: "var(--good)" }} />verified</span>
                <span><i style={{ background: "var(--crit)" }} />does not match</span>
              </span>
            </div>
          </div>
        </div>

        <div className={`card ${styles.side}`} style={{ padding: 18 }}>
          {q === "t1" ? (
            <>
              <div>
                <div className="label">P(fault stop within {w.horizon_h} h)</div>
                <div className={`${styles.big} num`} style={{ marginTop: 6 }}>{fmt(w.score, 2)}</div>
                <div className="meter" style={{ marginTop: 10 }} role="img" aria-label={pct(w.score)}><i style={{ width: `${Math.round(w.score * 100)}%` }} /></div>

              </div>
              <div>
                <div className="label" style={{ marginBottom: 8 }}>Subsystem probabilities</div>
                <div className={styles.probs}>
                  {probs.map(([c, p]) => (
                    <Row key={c} name={cls(c)} gold={c === w.gold} p={p} />
                  ))}
                </div>
                {w.gold !== "none" && <p className={styles.note} style={{ marginTop: 6 }}>Bold = what actually stopped.</p>}
              </div>
            </>
          ) : (
            <div>
              <div className="label">Subsystem named</div>
              <div className={styles.big} style={{ marginTop: 6, fontSize: 22 }}>{cls(label || "?")}</div>
            </div>
          )}
          <div>
            <div className="label" style={{ marginBottom: 8 }}>What actually happened</div>
            {w.gold === "none" ? (
              <dl className={styles.kv}>
                <dt>Next {w.horizon_h} h</dt><dd>no fault stop</dd>
                <dt>Right answer</dt><dd><span className={styles.msg}>Answer: no</span></dd>
              </dl>
            ) : (
              <>
                <div style={{ marginBottom: 8 }}><span className={styles.msg}>{o.message ?? ""}</span></div>
                <dl className={styles.kv}>
                  <dt>Began</dt><dd>+{dur(o.lead_time_min)} after the window</dd>
                  {o.duration_h != null && <><dt>Stopped for</dt><dd>{o.duration_h < 1 ? `${Math.round(o.duration_h * 60)} min` : `${fmt(o.duration_h, 1)} h`}</dd></>}
                  <dt>Subsystem</dt><dd>{cls(w.gold)}</dd>
                </dl>
              </>
            )}
          </div>
          <Link href="/results/" className="btn sm" style={{ alignSelf: "flex-start" }}>Results <IconArrow /></Link>
        </div>
      </div>
    </div>
  );
}

function Row({ name, gold, p }: { name: string; gold: boolean; p: number }) {
  return (
    <>
      <span className={`${styles.l} ${gold ? styles.gold : ""}`}>{name}</span>
      <span className={styles.bar}><i style={{ width: `${Math.round(p * 100)}%` }} /></span>
      <span className={`${styles.n} num`}>{fmt(p, 2)}</span>
    </>
  );
}
