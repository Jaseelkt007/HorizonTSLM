/** Shapes of data/demo_data.json and data/results_summary.json (written by scripts/build_demo_data.py). */

export type Farm = "kelmarsh" | "penmanshiel";
export type Split = "val" | "test_a" | "test_b";
export type Question = "t1" | "t3";

export interface Claim {
  start: number;
  end: number;
  ok: boolean;
}

export interface Outcome {
  message: string | null;
  lead_time_min: number | null;
  duration_h: number | null;
}

export interface ChannelMeta {
  name: string;
  label: string;
  unit: string;
}

export interface WindowRecord {
  id: string;
  farm: Farm;
  turbine: number;
  anchor: string;
  horizon_h: number;
  split: Split;
  state: "producing" | "idle_low_wind" | string;
  gold: string;
  pred: string;
  score: number;
  class_scores: Record<string, number>;
  text: string;
  claims: Claim[];
  t3_text: string | null;
  t3_claims: Claim[] | null;
  outcome: Outcome;
  facts: Record<string, number | string | null>;
  channels: Record<string, number[]>;
}

/** What the farm board and the window list need: everything but the signals and texts. */
export interface WindowSummary {
  id: string;
  farm: Farm;
  turbine: number;
  anchor: string;
  horizon_h: number;
  split: Split;
  state: string;
  gold: string;
  pred: string;
  score: number;
  outcome: Outcome;
  n_claims: number;
  n_ok: number;
  t3_pred: string | null;
}

export interface DemoData {
  meta: { channels: ChannelMeta[]; model: string; n: number };
  windows: WindowRecord[];
}

export interface ClassMetrics {
  n: number;
  recall_at_10far: number | null;
  hard_recall: number | null;
  subsystem_acc: number | null;
}

export interface HorizonMetrics {
  n: number;
  n_pos: number;
  auroc: number | null;
  recall_at_10far: number | null;
  recall_at_5far: number | null;
  hard_f1: number | null;
}

export interface Confusion {
  index: string[];
  columns: string[];
  data: number[][];
}

export interface SplitMetrics {
  n: number;
  n_pos: number;
  auroc: number | null;
  ap: number | null;
  recall_at_10far: number | null;
  recall_at_5far: number | null;
  hard_precision: number | null;
  hard_recall: number | null;
  hard_f1: number | null;
  hard_far: number | null;
  subsystem_acc: number | null;
  subsystem_macro_f1: number | null;
  per_class: Record<string, ClassMetrics>;
  confusion: Confusion | null;
  horizons: Record<string, HorizonMetrics>;
  t3?: {
    n: number;
    subsystem_acc: number | null;
    per_class: Record<string, { n: number; subsystem_acc: number | null }>;
  };
}

export interface Faithfulness {
  n_texts: number;
  claims: number;
  claim_precision: number;
  texts_with_wrong_claim: number;
  claims_per_text: number;
  conclusion_consistent: number;
  per_split: Record<string, { claim_precision: number; texts_with_wrong_claim: number; n: number }>;
}

export interface RunSummary {
  run: string;
  label: string;
  headline: boolean;
  splits: Partial<Record<Split, SplitMetrics>>;
  faithfulness?: Faithfulness;
}

export interface Baseline {
  label: string;
  source: string;
  test_a: { auroc: number; recall_at_10far: number; macro_f1: number };
  test_b: { auroc: number; recall_at_10far: number; macro_f1: number };
}

export interface ResultsSummary {
  runs: RunSummary[];
  floor: { label: string; auroc: number; recall_at_10far: number };
  baselines: Baseline[];
}
