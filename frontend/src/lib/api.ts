// An empty value is intentional for the same-origin Oracle deployment.
// Nullish fallback keeps local development pointed at the standalone API.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

/**
 * Pull a human-readable message out of a failed response. The backend answers
 * crashes with {detail, error} and validation problems with {status, errors}.
 */
async function failureMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body?.detail || body?.errors?.join("；") || body?.error || `服务返回 HTTP ${res.status}`;
  } catch {
    return `服务返回 HTTP ${res.status}`;
  }
}

export interface MalusRow {
  theta: number;
  i_left: number | null;
  i_right: number | null;
}

export interface HalfWaveInitial {
  c_deg: number | null;
  c_min: number;
  p2_deg: number | null;
  p2_min: number;
}

export interface HalfWaveRow {
  offset: number;
  c_deg: number | null;
  c_min: number;
  p2_deg: number | null;
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
  if (!res.ok) throw new Error(await failureMessage(res));
  const payload = await res.json();
  void trackEvent("calculation_run", "polarization", { status: payload.status });
  return payload;
}

export interface OCRCandidate {
  raw_text: string;
  value: string;
  confidence: number;
  bbox: number[][];
}

export interface TableOCRResponse {
  status: "success";
  experiment_id: string;
  table_id: string;
  detected_text_count: number;
  candidates: OCRCandidate[];
  ocr_provider?: string;
  ocr_model_version?: string;
}

export async function recognizeTableImage(
  image: File,
  experimentId: string,
  tableId: string
): Promise<TableOCRResponse> {
  const form = new FormData();
  form.append("image", image);
  form.append("experiment_id", experimentId);
  form.append("table_id", tableId);
  const res = await fetch(`${API_BASE}/api/ocr/table`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await failureMessage(res));
  return res.json();
}

export interface DataCollectionStatus {
  enabled: boolean;
  template_version: string;
}

export async function fetchDataCollectionStatus(): Promise<DataCollectionStatus> {
  const res = await fetch(`${API_BASE}/api/data-collection/status`);
  if (!res.ok) throw new Error(await failureMessage(res));
  return res.json();
}

export async function createDataCollectionSession(
  experimentId: string,
  templateVersion: string,
  image: File,
): Promise<{ session_id: string; revision: number }> {
  const form = new FormData();
  form.append("image", image);
  form.append("experiment_id", experimentId);
  form.append("template_version", templateVersion);
  form.append("consent", "true");
  const res = await fetch(`${API_BASE}/api/data-collection/sessions`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await failureMessage(res));
  return res.json();
}

export async function commitDataCollectionSession(
  sessionId: string,
  experimentId: string,
  templateVersion: string,
  confirmedData: object,
): Promise<{ revision: number; field_count: number }> {
  const res = await fetch(`${API_BASE}/api/data-collection/sessions/${sessionId}/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      experiment_id: experimentId,
      template_version: templateVersion,
      consent: true,
      confirmed_data: confirmedData,
    }),
  });
  if (!res.ok) throw new Error(await failureMessage(res));
  return res.json();
}

export async function deleteDataCollectionSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/data-collection/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) throw new Error(await failureMessage(res));
}

function anonymousSessionId(): string {
  if (typeof window === "undefined") return "server";
  const key = "physicslab-anonymous-session";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const created = typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.localStorage.setItem(key, created);
  return created;
}

export async function trackEvent(
  eventName: string,
  experimentId?: string,
  metadata: Record<string, unknown> = {},
): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/analytics/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_name: eventName,
        anonymous_session_id: anonymousSessionId(),
        experiment_id: experimentId,
        metadata,
        app_version: "2.0",
      }),
      keepalive: true,
    });
  } catch {
    // Analytics must never interrupt the experiment workflow.
  }
}

export async function submitOCRFeedback(feedback: {
  sample_id: string;
  experiment_id: string;
  field_id: string;
  prediction: string;
  confidence: number | null;
  confirmed_value: string;
  was_corrected: boolean;
  verified: boolean;
  consent: boolean;
  ocr_provider?: string;
  ocr_model_version?: string;
}): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/ocr/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...feedback,
        anonymous_session_id: anonymousSessionId(),
      }),
      keepalive: true,
    });
  } catch {
    // Feedback collection is optional and must not block data entry.
  }
}

export function getRecordSheetUrl(experimentId: string): string {
  return `${API_BASE}/api/record-sheets/${experimentId}`;
}

// ---------------------------------------------------------- file downloads

const EXP_CN: Record<string, string> = {
  polarization: "偏振光与双折射实验",
  "sound-light": "声速光速的测量",
  multimeter: "万用表的组装与校准",
  bridge: "交直流电桥的原理及应用",
  photoelectric: "光电效应与普朗克常数",
  "franck-hertz": "弗兰克-赫兹实验",
  "photoelectric-franck-hertz": "光电效应与弗兰克-赫兹实验",
  "solar-cell": "太阳能电池特性",
  gmr: "巨磁电阻效应及应用",
  nmr: "核磁共振实验",
  viscosity: "落球法测液体粘滞系数",
  "surface-tension": "液体表面张力系数测量",
  "thermal-conductivity": "稳态法测固体导热系数",
  michelson: "迈克尔逊干涉实验",
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
  void trackEvent("record_sheet_download", expId, { format: fmt });
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
  fmt: "docx" | "pdf",
  data: ProcessRequest,
  expId: string = "polarization"
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/experiments/${expId}/report?fmt=${fmt}`,
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
  const name = EXP_CN[expId] ?? "实验";
  triggerDownload(await res.blob(), `${name}-完整报告.${fmt}`);
  void trackEvent("report_export", expId, { format: fmt });
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
  method?: string;
  method_name?: string;
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
  if (!res.ok) throw new Error(await failureMessage(res));
  const payload = await res.json();
  void trackEvent("calculation_run", "sound-light", { method, status: payload.status });
  return payload;
}

export type SoundLightMethodData = Record<
  string,
  { rows: Record<string, (number | null)[]>; params: Record<string, number> }
>;

export async function downloadSoundLightReport(
  fmt: "docx" | "pdf",
  data: SoundLightMethodData
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/experiments/sound-light/report?fmt=${fmt}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
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
  triggerDownload(await res.blob(), `声速光速的测量-完整报告.${fmt}`);
}

// ------------------------------------------------ configuration-driven labs

export interface GenericColumn {
  key: string;
  label: string;
  unit: string;
  type?: "integer" | "float";
  required?: boolean;
  expected_range?: [number, number];
  decimal_places?: number;
}

export interface GenericParameter extends GenericColumn {
  default: number;
}

export interface GenericResultField {
  key: string;
  label: string;
  unit: string;
}

export interface GenericMethod {
  id: string;
  name: string;
  required: boolean;
  description: string;
  rowCount: number;
  columns: GenericColumn[];
  params?: GenericParameter[];
  prefill?: Record<string, number[]>;
  results: GenericResultField[];
}

export interface GenericExperimentConfig {
  id: string;
  name: string;
  category: string;
  description: string;
  processingTime: string;
  measurements: string[];
  methods: GenericMethod[];
}

export type GenericExperimentData = Record<
  string,
  { rows: Record<string, number | null>[]; params: Record<string, number> }
>;

export interface GenericProcessResponse {
  status: "success" | "validation_error";
  results: Record<string, Record<string, number>>;
  plots: Record<string, string>;
  derived: Record<string, Record<string, number>[]>;
  errors: string[];
  warnings?: string[];
  validation?: { valid: boolean; errors: unknown[]; warnings: unknown[] };
}

export async function fetchGenericConfig(id: string): Promise<GenericExperimentConfig> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/config`);
  if (!res.ok) throw new Error(`实验配置加载失败 (${res.status})`);
  return res.json();
}

export async function processGenericExperiment(
  id: string,
  data: GenericExperimentData
): Promise<GenericProcessResponse> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  if (!res.ok) throw new Error(`数据处理失败 (${res.status})`);
  const payload = await res.json();
  void trackEvent("calculation_run", id, { status: payload.status });
  if (payload.warnings?.length) {
    void trackEvent("validation_warning", id, { count: payload.warnings.length });
  }
  return payload;
}

export interface ValidationIssue {
  method_id: string;
  field_id: string;
  row: number | null;
  level: "error" | "warning";
  code: string;
  message: string;
}

export async function validateGenericExperiment(
  id: string,
  data: GenericExperimentData,
): Promise<{ valid: boolean; errors: ValidationIssue[]; warnings: ValidationIssue[] }> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  if (!res.ok) throw new Error(`数据校验失败 (${res.status})`);
  return res.json();
}

export async function downloadGenericReport(
  id: string,
  fmt: "docx" | "pdf",
  data: GenericExperimentData
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/report?fmt=${fmt}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || `报告生成失败 (${res.status})`);
  }
  triggerDownload(await res.blob(), `${EXP_CN[id] ?? "实验"}-完整报告.${fmt}`);
  void trackEvent("report_export", id, { format: fmt });
}
