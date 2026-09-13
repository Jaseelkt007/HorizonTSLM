"use client";

import { CHANNEL_SHORT, GROUPS, MAX_PINNED, SERIES } from "@/lib/labels";
import { fmtValue } from "@/lib/time";
import type { ChannelMeta } from "@/lib/types";

import styles from "./ChannelList.module.css";
import Sparkline from "./Sparkline";

interface Props {
  meta: ChannelMeta[];
  channels: Record<string, number[]>;
  cited: Set<string>;
  pinned: string[];
  onToggle: (name: string) => void;
}

/** All 19 channels, grouped by the subsystem they inform. Click a row to show it in the chart (up to three). */
export default function ChannelList({ meta, channels, cited, pinned, onToggle }: Props) {
  return (
    <div className={styles.wrap}>
      <div className={styles.list}>
        {GROUPS.map((g) => (
          <div key={g.title}>
            <div className={styles.grp} title={g.sub}>{g.title}</div>
            {g.channels.map((name) => {
              const m = meta.find((c) => c.name === name);
              const y = channels[name];
              if (!m || !y) return null;
              const k = pinned.indexOf(name);
              const color = k >= 0 ? SERIES[k] : undefined;
              return (
                <button
                  key={name}
                  type="button"
                  className={`${styles.row} ${k >= 0 ? styles.pinned : ""}`}
                  style={color ? ({ "--c": color } as React.CSSProperties) : undefined}
                  aria-pressed={k >= 0}
                  onClick={() => onToggle(name)}
                  title={`${m.label} — click to ${k >= 0 ? "remove from" : "show in"} the chart`}
                >
                  <span className={styles.bar} />
                  <span className={styles.name}>
                    <span>{CHANNEL_SHORT[name] ?? m.label}</span>
                    {cited.has(name) && <i className={styles.cited} title="cited in the explanation" />}
                  </span>
                  <Sparkline values={y} color={color ?? "var(--ink-4)"} />
                  <span className={styles.val}>{fmtValue(y[y.length - 1])} <small>{m.unit}</small></span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div className={styles.foot}>
        <span>Click a channel to chart it (up to {MAX_PINNED}).</span>
        <span><i className={styles.cited} style={{ display: "inline-block", marginRight: 5, verticalAlign: 1 }} />cited in the explanation</span>
      </div>
    </div>
  );
}
