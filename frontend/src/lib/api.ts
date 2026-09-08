const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface MalusRow {
  theta: number;
  i_left: number | null;
  i_right: number | null;
}

export interface HalfWaveInitial {
  c_deg: number;
  c_min: number;
  p2_deg: number;
  p2_min: number;
}

export interface HalfWaveRow {
  offset: number;
  c_deg: number;
  c_min: number;
  p2_deg: number;
  p2_min: number;
}

export interface QuarterWaveRow {
  phi: number;
  i_raw: number | null;
}

export interface CircularRow {
  angle: number;
  i_raw: number | null;
}

export interface ProcessRequest {
  bg_uw: number;
  theta_qwp: number;
  malus?: { rows: MalusRow[] };
  halfwave?: { initial: HalfWaveInitial; rows: HalfWaveRow[] };
  quarterwave?: { rows: QuarterWaveRow[] };
  circular?: { rows: CircularRow[] };
}

export interface ProcessResponse {
  status: "success" | "validation_error" | "calculation_error";
  results: Record<string, Record<string, number>>;
  plots: Record<string, string>;
  errors?: string[];
  error?: string;
}

export interface ExperimentInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  sub_experiments: { id: string; name: string; required: boolean }[];
  measurements: { key: string; label: string; unit: string }[];
  record_sheet: string;
  processing_time: string;
}

export async function fetchExperiments(): Promise<ExperimentInfo[]> {
  const res = await fetch(`${API_BASE}/api/experiments`);
  const data = await res.json();
  return data.experiments;
}

export async function processPolarization(
  data: ProcessRequest
): Promise<ProcessResponse> {
  const res = await fetch(`${API_BASE}/api/experiments/polarization/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export function getRecordSheetUrl(experimentId: string): string {
  return `${API_BASE}/api/record-sheets/${experimentId}`;
}
