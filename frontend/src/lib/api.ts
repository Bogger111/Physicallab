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

// ---------------------------------------------------------- file downloads

const EXP_CN: Record<string, string> = {
  polarization: "偏振光与双折射实验",
  "sound-light": "声速光速的测量",
};

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export async function downloadRecordSheet(
  fmt: "docx" | "pdf",
  expId: string = "polarization"
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/record-sheets/${expId}.${fmt}`);
  if (!res.ok) throw new Error(`记录表下载失败 (${res.status})`);
  const name = EXP_CN[expId] ?? "实验";
  triggerDownload(await res.blob(), `${name}-数据记录表.${fmt}`);
}

export async function previewRecordSheet(
  expId: string = "polarization"
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/record-sheets/${expId}.pdf`);
  if (!res.ok) throw new Error(`记录表生成失败 (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export async function downloadReport(
  part: "basic" | "advanced",
  fmt: "docx" | "pdf",
  data: ProcessRequest,
  expId: string = "polarization"
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/experiments/${expId}/report?part=${part}&fmt=${fmt}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    let msg = `报告生成失败 (${res.status})`;
    try {
      const j = await res.json();
      if (j.detail) msg = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const label = part === "basic" ? "基准部分" : "拓展部分";
  const name = EXP_CN[expId] ?? "实验";
  triggerDownload(await res.blob(), `${name}-报告-${label}.${fmt}`);
}

// ---------------------------------------------------------- exp02 sound-light

export interface SoundLightResultField {
  key: string;
  label: string;
  value: number;
  unit: string;
}

export interface SoundLightProcessResponse {
  status: "success" | "validation_error" | "calculation_error";
  results: SoundLightResultField[];
  plots: Record<string, string>;
  errors?: string[];
  error?: string;
}

export async function processSoundLight(
  method: string,
  rows: Record<string, (number | null)[]>,
  params: Record<string, number>
): Promise<SoundLightProcessResponse> {
  const res = await fetch(`${API_BASE}/api/experiments/sound-light/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, rows, params }),
  });
  return res.json();
}

export type SoundLightMethodData = Record<
  string,
  { rows: Record<string, (number | null)[]>; params: Record<string, number> }
>;

export async function downloadSoundLightReport(
  part: "basic" | "advanced",
  fmt: "docx" | "pdf",
  data: SoundLightMethodData
): Promise<void> {
  await downloadReport(part, fmt, data as unknown as ProcessRequest, "sound-light");
}
