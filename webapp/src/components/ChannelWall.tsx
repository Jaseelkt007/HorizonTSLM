import { CITES, GROUPS } from "@/lib/labels";
import type { ChannelMeta } from "@/lib/types";

import ChannelChart from "./ChannelChart";
import styles from "./Chart.module.css";

/** The 19 channels as small multiples, grouped by the subsystem they inform; cited ones outlined. */
export default function ChannelWall({ channels, meta, body }: { channels: Record<string, number[]>; meta: ChannelMeta[]; body: string }) {
  return (
    <div className={styles.wall}>
      {GROUPS.map((g) => (
        <GroupRows key={g.title} title={g.title} sub={g.sub}>
          {g.channels.map((name) => {
            const m = meta.find((c) => c.name === name);
            const y = channels[name];
            if (!m || !y) return null;
            return <ChannelChart key={name} meta={m} values={y} cited={!!CITES[name]?.test(body)} />;
          })}
        </GroupRows>
      ))}
    </div>
  );
}

function GroupRows({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <>
      <div className={styles.grp}>
        <h4>{title}</h4>
        <span>{sub}</span>
      </div>
      {children}
    </>
  );
}
