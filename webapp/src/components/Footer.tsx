import styles from "./TopBar.module.css";

export default function Footer({ nWindows, model }: { nWindows: number; model: string }) {
  return (
    <p className={styles.foot}>
      Every figure on this site is read from <code>data/demo_data.json</code> ({nWindows} held-out windows, model <code>{model}</code>) and{" "}
      <code>data/results_summary.json</code>, both written by <code>scripts/build_demo_data.py</code> from the run outputs in <code>docs/results/</code> and
      the XGBoost table in <code>docs/benchmark.md</code>. Nothing is typed by hand. Data: Cubico Penmanshiel and Kelmarsh SCADA (Zenodo, CC-BY-4.0).
    </p>
  );
}
