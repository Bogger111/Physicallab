"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Table2,
  ChartSpline,
  FileDown,
  Download,
  Eye,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Sigma,
  Waves,
  Clock3,
  Ruler,
  Gauge,
  Orbit,
  CircleDashed,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getInputRange, isOutsideRange, rangeLabel, type InputRangeHint } from "@/lib/input-ranges";
import DataInputTable from "@/components/workspace/DataInputTable";
import { SOUND_LIGHT_WORKSPACE_STEPS } from "@/components/workspace/workspace-entry-flow";
import soundLightConfig from "../../../../backend/experiments/soundlight/config.json";
import {
  API_BASE,
  processSoundLight,
  downloadRecordSheet,
  previewRecordSheet,
  downloadSoundLightReport,
  type SoundLightProcessResponse,
} from "@/lib/api";

const EXP_ID = "sound-light";

type Step = (typeof SOUND_LIGHT_WORKSPACE_STEPS)[number];

const STEP_META: Record<Step, { label: string; icon: React.ElementType }> = {
  input: { label: "录入数据", icon: Table2 },
  results: { label: "结果", icon: ChartSpline },
};

const STEPS = SOUND_LIGHT_WORKSPACE_STEPS.map((id) => ({ id, ...STEP_META[id] }));

interface ColDef {
  label: string;
  readOnly?: boolean;
  key?: string; // column key sent to backend (editable columns)
  unit?: string;
  range?: InputRangeHint;
}

interface MethodSpec {
  id: string;
  name: string;
  required: boolean;
  desc: string;
  tables: { title?: string; note?: string; rows: number; cols: ColDef[] }[];
  params: { key: string; label: string; unit: string; def: string; range?: InputRangeHint }[];
}

const METHOD_LAYOUTS: MethodSpec[] = [
  // ── 实验一：超声声速测量 ──
  {
    id: "air_resonance",
    name: "① 共振干涉法（空气）",
    required: true,
    desc: "实验一 · 必做。S2 同方向连续移动，记录 12 个驻波共振位置（相邻间距 ≈ λ/2），逐差法求 Δl̄。",
    tables: [
      {
        note: "温度用于理论声速修正 v = 331.45 × √(1 + t/273.15)",
        rows: 12,
        cols: [
          { label: "序号", readOnly: true },
          { label: "空气中共振法 l (mm)", key: "l" },
        ],
      },
    ],
    params: [
      { key: "temperature_degC", label: "环境温度 t", unit: "°C", def: "25" },
      { key: "f_khz", label: "共振频率 f", unit: "kHz", def: "38" },
    ],
  },
  {
    id: "water_phase",
    name: "② 相位比较法（水）",
    required: true,
    desc: "实验一 · 必做。水中移动 S2 至李萨如为直线的 12 个相位匹配位置（与空气共用表 1-1），逐差法处理并计算 A 类不确定度。",
    tables: [
      {
        note: "频率约 1 MHz（以实际为准）",
        rows: 12,
        cols: [
          { label: "序号", readOnly: true },
          { label: "水中相位法 l (mm)", key: "l" },
        ],
      },
    ],
    params: [{ key: "f_mhz", label: "频率 f", unit: "MHz", def: "1" }],
  },
  {
    id: "tof",
    name: "③ 时差法 · 水",
    required: false,
    desc: "实验一 · 选做。脉冲波模式测水中声速：S2 每次移动等间距 20 mm，连续记录 12 组距离 L 与飞行时间 T，逐点 v = L/T。",
    tables: [
      {
        note: "每次移动 20 mm，共 12 组",
        rows: 12,
        cols: [
          { label: "序号", readOnly: true },
          { label: "距离 L (mm)", key: "L" },
          { label: "飞行时间 T (μs)", key: "T" },
        ],
      },
    ],
    params: [],
  },
  // ── 实验二：光速测量 ──
  {
    id: "light_sine",
    name: "① 相位法（正弦波）",
    required: true,
    desc: "实验二 · 必做。差频正弦相位法：先测 3 组差频周期 T，再移动反射镜记录 3 组相位差 Δt 与位置 x₁→x₂（表 2-1 / 2-2）。",
    tables: [
      {
        title: "表 2-1 周期测量",
        rows: 3,
        cols: [
          { label: "序号", readOnly: true },
          { label: "周期 T (μs)", key: "T" },
        ],
      },
      {
        title: "表 2-2 相位移动",
        rows: 3,
        cols: [
          { label: "序号", readOnly: true },
          { label: "相位差 Δt (μs)", key: "dt" },
          { label: "x₁ (mm)", key: "x1" },
          { label: "x₂ (mm)", key: "x2" },
        ],
      },
    ],
    params: [{ key: "f_mhz", label: "调制频率 f_t", unit: "MHz", def: "150" }],
  },
  {
    id: "light_square",
    name: "② 相位法（方波）",
    required: false,
    desc: "实验二 · 选做。示波器换方波挡位，方法与正弦波完全相同：同测差频周期 T 与 3 组相位差 Δt、x₁→x₂。",
    tables: [
      {
        title: "周期测量",
        rows: 3,
        cols: [
          { label: "序号", readOnly: true },
          { label: "周期 T (μs)", key: "T" },
        ],
      },
      {
        title: "相位移动",
        rows: 3,
        cols: [
          { label: "序号", readOnly: true },
          { label: "相位差 Δt (μs)", key: "dt" },
          { label: "x₁ (mm)", key: "x1" },
          { label: "x₂ (mm)", key: "x2" },
        ],
      },
    ],
    params: [{ key: "f_mhz", label: "调制频率 f_t", unit: "MHz", def: "150" }],
  },
  {
    id: "light_lissajous",
    name: "③ 李萨如图形法",
    required: true,
    desc: "实验二 · 必做。X-Y 模式：反射镜从直线图形移动到反斜率直线（π 相位差，对应 Δx = λ/4），共 3 组（表 2-3）。",
    tables: [
      {
        rows: 3,
        cols: [
          { label: "序号", readOnly: true },
          { label: "x₁ (mm)", key: "x1" },
          { label: "x₂ (mm)", key: "x2" },
        ],
      },
    ],
    params: [{ key: "f_mhz", label: "调制频率 f_t", unit: "MHz", def: "150" }],
  },
];

interface SourceMethodConfig {
  id: string;
  type: "required" | "optional";
  table_cols: { key: string; label: string; unit: string; count: number }[];
  params: { key: string; label: string; unit: string; default: number }[];
}

// Field keys, units, row counts, required flags and defaults come from the
// backend config. This file keeps only UI grouping/copy such as “表 2-1”.
const METHODS: MethodSpec[] = (soundLightConfig as SourceMethodConfig[]).map((source) => {
  const layout = METHOD_LAYOUTS.find((item) => item.id === source.id);
  if (!layout) throw new Error(`缺少方法 ${source.id} 的前端布局定义`);
  const columns = new Map(source.table_cols.map((column) => [column.key, column]));
  return {
    ...layout,
    required: source.type === "required",
    tables: layout.tables.map((table) => {
      const sourceColumns = table.cols
        .filter((column) => column.key)
        .map((column) => columns.get(column.key!))
        .filter((column): column is SourceMethodConfig["table_cols"][number] => Boolean(column));
      return {
        ...table,
        rows: Math.max(...sourceColumns.map((column) => column.count)),
        cols: table.cols.map((column) => {
          if (!column.key) return column;
          const sourceColumn = columns.get(column.key);
          if (!sourceColumn) throw new Error(`方法 ${source.id} 缺少字段 ${column.key}`);
          return {
            ...column,
            label: `${sourceColumn.label} (${sourceColumn.unit})`,
            unit: sourceColumn.unit,
            range: getInputRange(EXP_ID, source.id, column.key),
          };
        }),
      };
    }),
    params: source.params.map((param) => ({
      key: param.key,
      label: param.label,
      unit: param.unit,
      def: String(param.default),
      range: getInputRange(EXP_ID, source.id, param.key),
    })),
  };
});

const METHOD_ICON: Record<string, React.ElementType> = {
  air_resonance: Waves,
  water_phase: Waves,
  tof: Clock3,
  light_sine: Gauge,
  light_square: Gauge,
  light_lissajous: Orbit,
};

function _e(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "";
  const n = v as number;
  if (Number.isInteger(n)) return String(n);
  if (Math.abs(n) >= 100) return n.toFixed(2).replace(/\.?0+$/, "");
  if (Math.abs(n) >= 1) return n.toFixed(3).replace(/\.?0+$/, "");
  return n.toFixed(4).replace(/\.?0+$/, "");
}

function DataEcho({
  methodId,
  rowsPayload,
}: {
  methodId: string;
  rowsPayload: Record<string, (number | null)[]>;
}) {
  const spec = METHODS.find((m) => m.id === methodId);
  if (!spec) return null;
  // base columns in display order
  const base: { label: string; key: string }[] = [];
  spec.tables.forEach((t) =>
    t.cols.forEach((c) => {
      if (!c.readOnly && c.key) base.push({ label: c.label, key: c.key });
    })
  );
  const extra: string[] = [];
  if (methodId === "light_sine" || methodId === "light_square" || methodId === "light_lissajous")
    extra.push("Δx (mm)");
  if (methodId === "light_sine" || methodId === "light_square") extra.push("Δx/Δt (mm/μs)");
  if (methodId === "tof") extra.push("v = L/T (m/s)");
  const n =
    Math.max(1, ...base.map((b) => rowsPayload[b.key]?.length ?? 0), spec.tables.reduce((a, t) => Math.max(a, t.rows), 0));
  const num = (k: string, i: number) => rowsPayload[k]?.[i] ?? null;
  return (
    <div className="border-t border-stone-100 bg-white p-5 sm:p-6">
      <p className="mb-3 flex items-center gap-2 text-sm font-bold text-stone-700">
        <Table2 className="h-4 w-4 text-indigo-600" />
        已录入数据（含计算列）
      </p>
      <div className="overflow-x-auto rounded-lg border border-stone-200">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="border-b border-stone-200 bg-stone-50 px-3 py-2 text-left text-xs font-bold text-stone-500">
                次数
              </th>
              {base.map((b) => (
                <th key={b.key} className="border-b border-stone-200 bg-stone-50 px-3 py-2 text-right text-xs font-bold text-stone-500">
                  {b.label}
                </th>
              ))}
              {extra.map((e) => (
                <th key={e} className="border-b border-stone-200 bg-indigo-50/70 px-3 py-2 text-right text-xs font-bold text-indigo-600">
                  {e}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: n }, (_, i) => {
              const x1 = num("x1", i);
              const x2 = num("x2", i);
              const dt = num("dt", i);
              const L = num("L", i);
              const T = num("T", i);
              let dx: number | null = null;
              if (x1 !== null && x2 !== null) dx = Math.abs(x2 - x1);
              let ratio: number | null = null;
              if (dx !== null && dt !== null && dt > 0) ratio = dx / dt;
              let vi: number | null = null;
              if (L !== null && T !== null && T > 0) vi = (L * 1e-3) / (T * 1e-6);
              return (
                <tr key={i} className="odd:bg-white even:bg-stone-50/40">
                  <td className="border-b border-stone-100 px-3 py-1.5 text-xs font-medium text-stone-400">
                    {i + 1}
                  </td>
                  {base.map((b) => (
                    <td key={b.key} className="border-b border-stone-100 px-3 py-1.5 text-right font-medium tabular-nums text-stone-800">
                      {_e(num(b.key, i))}
                    </td>
                  ))}
                  {extra.map((e) => {
                    const val = e.startsWith("Δx (")
                      ? dx
                      : e.startsWith("Δx/Δt")
                        ? ratio
                        : vi;
                    return (
                      <td key={e} className="border-b border-stone-100 bg-indigo-50/30 px-3 py-1.5 text-right font-semibold tabular-nums text-indigo-800">
                        {_e(val)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function makeRows(rows: number, extraCols: number): string[][] {
  return Array.from({ length: rows }, (_, i) => [
    String(i + 1),
    ...Array.from({ length: extraCols }, () => ""),
  ]);
}

export default function SoundLightWorkspace() {
  const [step, setStep] = useState<Step>(SOUND_LIGHT_WORKSPACE_STEPS[0]);
  const [method, setMethod] = useState<string>("air_resonance");
  // cell data: key `${method}#${tableIndex}`
  const [cell, setCell] = useState<Record<string, string[][]>>({});
  const [params, setParams] = useState<Record<string, Record<string, string>>>({});
  const [busy, setBusy] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);
  // per processed method: response + submitted data
  const [processed, setProcessed] = useState<
    Record<
      string,
      {
        res: SoundLightProcessResponse;
        rows: Record<string, (number | null)[]>;
        params: Record<string, number>;
      }
    >
  >({});
  const [currentResult, setCurrentResult] = useState<string | null>(null);

  const spec = METHODS.find((m) => m.id === method)!;

  const getRows = (mId: string, ti: number): string[][] => {
    const mspec = METHODS.find((m) => m.id === mId)!;
    const table = mspec.tables[ti];
    const key = `${mId}#${ti}`;
    if (!cell[key]) {
      const editable = table.cols.filter((c) => !c.readOnly).length;
      return makeRows(table.rows, editable);
    }
    return cell[key];
  };

  const setRows = (mId: string, ti: number, data: string[][]) =>
    setCell((prev) => ({ ...prev, [`${mId}#${ti}`]: data }));

  const getParams = (mId: string): Record<string, string> => {
    const mspec = METHODS.find((m) => m.id === mId)!;
    const cur = params[mId] ?? {};
    const out: Record<string, string> = {};
    mspec.params.forEach((p) => {
      out[p.key] = cur[p.key] ?? p.def;
    });
    return out;
  };

  const buildPayload = useCallback(
    (mId: string) => {
      const mspec = METHODS.find((m) => m.id === mId)!;
      const rowsOut: Record<string, (number | null)[]> = {};
      mspec.tables.forEach((table, ti) => {
        const rows = getRows(mId, ti);
        table.cols.forEach((col, ci) => {
          if (!col.key || col.readOnly) return;
          rowsOut[col.key] = rows.map((r) => {
            const v = r[ci];
            if (v === undefined || v.trim() === "") return null;
            const n = parseFloat(v);
            return Number.isFinite(n) ? n : null;
          });
        });
      });
      const pOut: Record<string, number> = {};
      Object.entries(getParams(mId)).forEach(([k, v]) => {
        const n = parseFloat(v);
        if (Number.isFinite(n)) pOut[k] = n;
      });
      return { rows: rowsOut, params: pOut };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [cell, params, method]
  );

  // 数据是否已填满（无需预先逐方法计算，报告生成时后端会内部重算）
  const isMethodFilled = (mId: string): boolean => {
    const mspec = METHODS.find((m) => m.id === mId);
    if (!mspec) return false;
    return mspec.tables.every((table, ti) => {
      const rows = getRows(mId, ti);
      return table.cols.every((col, ci) => {
        if (!col.key || col.readOnly) return true;
        return rows.every((r) => (r[ci] ?? "").trim() !== "");
      });
    });
  };
  const filledAllReportData = () => {
    const out: Record<string, { rows: Record<string, (number | null)[]>; params: Record<string, number> }> = {};
    METHODS.forEach((m) => {
      if (isMethodFilled(m.id)) {
        const p = buildPayload(m.id);
        out[m.id] = { rows: p.rows, params: p.params };
      }
    });
    return out;
  };
  const requiredMethods = METHODS.filter((m) => m.required);
  const requiredFilledCount = requiredMethods.filter((m) => isMethodFilled(m.id)).length;
  const requiredAllFilled = requiredFilledCount === requiredMethods.length;
  const missingFill = requiredMethods
    .filter((m) => !isMethodFilled(m.id))
    .map((m) => m.name);

  const handleProcess = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = buildPayload(method);
      const res = await processSoundLight(method, payload.rows, payload.params);
      if (res.status !== "success") {
        setError(res.errors?.join("；") || res.error || "数据处理失败");
        return;
      }
      setProcessed((prev) => ({ ...prev, [method]: { res, ...payload } }));
      setCurrentResult(method);
      setStep("results");
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(
        `计算未完成：${detail}。服务地址 ${API_BASE}，首次访问可能有约 10 秒冷启动，稍等后重试即可。` +
          "已录入的数据仍保留在本页，不需要重新输入。"
      );
    } finally {
      setBusy(false);
    }
  };

  const runDownload = async (key: string, action: () => Promise<void>) => {
    if (busyKey) return;
    setBusyKey(key);
    setDlError(null);
    try {
      await action();
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "下载失败");
    } finally {
      setBusyKey(null);
    }
  };

  const processedKeys = Object.keys(processed);
  const reportData = Object.fromEntries(
    processedKeys.map((k) => [k, { rows: processed[k].rows, params: processed[k].params }])
  );
  const basicReady = METHODS.filter((m) => m.required).every(
    (m) => !!processed[m.id]
  );
  const missingRequired = METHODS.filter(
    (m) => m.required && !processed[m.id]
  ).map((m) => m.name);
  const cur = currentResult && processed[currentResult] ? processed[currentResult].res : null;
  const stepIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <div className="min-h-screen">
      {/* top bar */}
      <div className="border-b border-stone-200/70 bg-white">
        <div className="container-x flex h-14 items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/experiments/sound-light"
              className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-[13px] font-medium text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-800"
            >
              <ArrowLeft className="h-4 w-4" />
              返回
            </Link>
            <span aria-hidden className="h-4 w-px shrink-0 bg-stone-200" />
            <div className="flex min-w-0 items-baseline gap-2">
              <h1 className="truncate text-sm font-bold text-stone-900">声速光速的测量</h1>
              <span className="hidden shrink-0 text-xs font-medium text-stone-400 sm:inline">
                数据处理工作台
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* stepper */}
      <div className="border-b border-stone-200/60 bg-white/70 backdrop-blur">
        <div className="container-x flex items-center py-4">
          {STEPS.map((s, i) => {
            const isActive = s.id === step;
            const isCompleted = i < stepIndex;
            const Icon = s.icon;
            return (
              <div key={s.id} className={cn("flex items-center", i > 0 && "flex-1")}>
                {i > 0 && (
                  <div className="relative mx-3 h-[2px] flex-1 overflow-hidden rounded-full bg-stone-200 sm:mx-4">
                    {isCompleted && (
                      <div className="absolute inset-0 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" />
                    )}
                  </div>
                )}
                <button
                  onClick={() => isCompleted && setStep(s.id)}
                  disabled={!isCompleted && !isActive}
                  aria-current={isActive ? "step" : undefined}
                  className={cn("flex items-center gap-2.5 rounded-full", (isCompleted || isActive) && "cursor-pointer")}
                >
                  <span
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all",
                      isCompleted &&
                        "bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/25",
                      isActive &&
                        "bg-indigo-600 text-white shadow-md shadow-indigo-600/30 ring-4 ring-indigo-500/20",
                      !isCompleted && !isActive && "bg-stone-100 text-stone-400"
                    )}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="h-[18px] w-[18px]" strokeWidth={2.4} />
                    ) : (
                      <Icon className="h-[17px] w-[17px]" strokeWidth={2.1} />
                    )}
                  </span>
                  <span
                    className={cn(
                      "hidden text-sm font-semibold sm:inline",
                      isActive ? "text-stone-900" : isCompleted ? "text-stone-600" : "text-stone-400"
                    )}
                  >
                    {s.label}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="container-x py-8 sm:py-10">
        {/* ---------- STEP 1 · input ---------- */}
        {step === "input" && (
          <div className="mx-auto max-w-4xl animate-rise-in">
            <div className="mb-7">
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.24em] text-indigo-500">
                Step 01 · 录入数据
              </p>
              <h2 className="text-2xl font-extrabold tracking-tight text-stone-900">
                选择测量方法，录入读数
              </h2>
              <p className="mt-1 text-sm text-stone-500">
                逐方法填数据即可，无需逐个先算：4 个必做填完就能「一口气」生成完整报告（表格 → 图片 → 数据处理 → 拓展与总结）；想先看某个方法的结果，可单独点它的「生成结果」。选做方法填入后并入完整报告，否则自动跳过。
              </p>
            </div>

            <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-stone-200 bg-stone-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-bold text-stone-800">需要纸质记录表？</p>
                <p className="mt-0.5 text-xs text-stone-400">无需离开录入页，可直接预览或下载。</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => runDownload("preview", () => previewRecordSheet(EXP_ID))}
                  disabled={busyKey !== null}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-3 text-xs font-semibold text-stone-700 disabled:opacity-50"
                >
                  <Eye className="h-3.5 w-3.5" />预览
                </button>
                <button
                  onClick={() => runDownload("record-docx", () => downloadRecordSheet("docx", EXP_ID))}
                  disabled={busyKey !== null}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-stone-900 px-3 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {busyKey === "record-docx" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                  记录表 Word
                </button>
                <button
                  onClick={() => runDownload("record-pdf", () => downloadRecordSheet("pdf", EXP_ID))}
                  disabled={busyKey !== null}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {busyKey === "record-pdf" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                  记录表 PDF
                </button>
              </div>
            </div>
            {dlError && (
              <p className="mb-6 text-xs font-medium text-red-500" role="alert">
                {dlError}
              </p>
            )}

            {/* method selector */}
            <div className="mb-6 flex flex-wrap gap-2" role="tablist" aria-label="测量方法">
              {METHODS.map((m) => {
                const active = method === m.id;
                const done = !!processed[m.id] || isMethodFilled(m.id);
                return (
                  <button
                    key={m.id}
                    role="tab"
                    aria-selected={active}
                    onClick={() => setMethod(m.id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-[13px] font-semibold transition-all",
                      active
                        ? "border-stone-900 bg-stone-900 text-white shadow-md shadow-stone-900/20"
                        : "border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-stone-800"
                    )}
                  >
                    {done && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                    <span>{m.name}</span>
                    {!m.required && (
                      <span className="font-normal opacity-60">· 选做</span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* one-click unified report */}
            <div
              className={cn(
                "mb-6 flex flex-col gap-4 rounded-2xl border p-5 sm:flex-row sm:items-center",
                requiredAllFilled
                  ? "border-emerald-200 bg-emerald-50/50"
                  : "border-stone-200 bg-stone-50/60"
              )}
            >
              <div className="flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-bold text-stone-900">
                  {requiredAllFilled ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      必做数据已齐（{requiredFilledCount}/{requiredMethods.length}）——可一键生成完整报告
                    </>
                  ) : (
                    <>
                      <CircleDashed className="h-4 w-4 text-amber-500" />
                      必做进度 {requiredFilledCount}/{requiredMethods.length}
                    </>
                  )}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
                  完整报告按四部分排列：全部表格 → 全部图片 → 详细数据处理 → 拓展、建议、误差分析与总结。
                  {!requiredAllFilled && missingFill.length > 0 && (
                    <span className="mt-0.5 block font-semibold text-amber-600">
                      还差：{missingFill.join("、")}
                    </span>
                  )}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() =>
                    runDownload("quick-report-docx", () =>
                      downloadSoundLightReport("docx", filledAllReportData())
                    )
                  }
                  disabled={busyKey !== null || !requiredAllFilled}
                  className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-stone-900 px-4 text-xs font-semibold text-white transition-colors hover:bg-stone-700 disabled:opacity-40"
                >
                  {busyKey === "quick-report-docx" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                  完整 · Word
                </button>
                <button
                  onClick={() =>
                    runDownload("quick-report-pdf", () =>
                      downloadSoundLightReport("pdf", filledAllReportData())
                    )
                  }
                  disabled={busyKey !== null || !requiredAllFilled}
                  className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-40"
                >
                  {busyKey === "quick-report-pdf" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                  完整 · PDF
                </button>
              </div>
            </div>

            {/* current method panel */}
            <div key={method} className="card animate-fade-in overflow-hidden shadow-soft">
              <div className="flex items-center gap-3 border-b border-stone-100 bg-stone-50/60 px-6 py-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25">
                  {(() => {
                    const Icon = METHOD_ICON[spec.id] ?? Ruler;
                    return <Icon className="h-[18px] w-[18px]" strokeWidth={2} />;
                  })()}
                </span>
                <div className="min-w-0">
                  <h3 className="text-[15px] font-bold text-stone-900">{spec.name}</h3>
                  <p className="truncate text-xs leading-relaxed text-stone-500">{spec.desc}</p>
                </div>
                {spec.required ? (
                  <span className="ml-auto shrink-0 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600">必做</span>
                ) : (
                  <span className="ml-auto shrink-0 rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-bold text-stone-400">选做</span>
                )}
              </div>

              <div className="space-y-5 p-6">
                {/* params */}
                {spec.params.length > 0 && (
                  <div className="flex flex-wrap items-end gap-5 rounded-xl border border-stone-200/80 bg-stone-50/50 p-4">
                    <p className="w-full text-xs font-bold text-stone-500">实验参数</p>
                    {spec.params.map((p) => (
                      <label key={p.key} className="flex flex-col gap-1.5">
                        <span className="text-xs font-medium text-stone-400">
                          {p.label} ({p.unit})
                        </span>
                        {rangeLabel(p.range, p.unit) && (
                          <span className="text-[10px] font-medium text-amber-600">{rangeLabel(p.range, p.unit)}</span>
                        )}
                        <input
                          type="number"
                          step="any"
                          value={getParams(method)[p.key]}
                          onChange={(e) =>
                            setParams((prev) => ({
                              ...prev,
                              [method]: { ...(prev[method] ?? {}), [p.key]: e.target.value },
                            }))
                          }
                          onWheel={(e) => e.currentTarget.blur()}
                          aria-invalid={isOutsideRange(getParams(method)[p.key], p.range) || undefined}
                          className={cn(
                            "h-9 w-28 rounded-lg border bg-white px-3 text-right text-sm font-medium tabular-nums shadow-sm outline-none transition-all",
                            isOutsideRange(getParams(method)[p.key], p.range)
                              ? "border-amber-300 bg-amber-50 text-amber-900 focus:ring-4 focus:ring-amber-500/10"
                              : "border-stone-200 text-stone-800 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                          )}
                        />
                      </label>
                    ))}
                  </div>
                )}

                {/* tables */}
                {spec.tables.map((table, ti) => (
                  <div key={ti}>
                    {table.title && (
                      <p className="mb-2 text-sm font-bold text-stone-700">{table.title}</p>
                    )}
                    {table.note && (
                      <p className="mb-2 rounded-lg bg-indigo-50/80 px-3 py-2 text-xs leading-relaxed text-indigo-900/80 ring-1 ring-inset ring-indigo-100">
                        {table.note}
                      </p>
                    )}
                    <DataInputTable
                      headers={table.cols.map((c) => ({
                        label: c.label,
                        readOnly: c.readOnly,
                        range: c.range,
                        unit: c.unit,
                      }))}
                      data={getRows(method, ti)}
                      onChange={(d) => setRows(method, ti, d)}
                      ocr={{ experimentId: EXP_ID, tableId: `${method}-${ti}` }}
                    />
                  </div>
                ))}
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="mt-5 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-relaxed text-red-700"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-8 flex justify-end">
              <button
                onClick={handleProcess}
                disabled={busy}
                className="group inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-7 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> 正在计算…
                  </>
                ) : (
                  <>
                    {spec.name.split("（")[0]} · 生成结果
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ---------- STEP 3 · results ---------- */}
        {step === "results" && (
          <div className="mx-auto max-w-4xl animate-rise-in">
            {cur ? (
              <>
                <div className="mb-6 flex flex-col items-start justify-between gap-4 rounded-2xl border border-emerald-200/70 bg-gradient-to-r from-emerald-50 via-white to-emerald-50/50 p-6 sm:flex-row sm:items-center">
                  <div className="flex items-center gap-4">
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/30">
                      <CheckCircle2 className="h-6 w-6" />
                    </span>
                    <div>
                      <p className="text-lg font-extrabold tracking-tight text-stone-900">
                        {METHODS.find((m) => m.id === currentResult)?.name} · 计算完成
                      </p>
                      <p className="mt-0.5 text-sm text-stone-500">
                        已处理 {processedKeys.length}/5 个方法，可继续录入其余方法或下载报告
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setStep("input")}
                    className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-700 transition-colors hover:border-stone-400 hover:text-stone-900"
                  >
                    <Sigma className="h-4 w-4" /> 继续录入其他方法
                  </button>
                </div>

                <div className="card overflow-hidden shadow-soft">
                  <div className="flex items-center gap-3 border-b border-stone-100 bg-stone-50/60 px-6 py-4">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25">
                      {(() => {
                        const Icon = METHOD_ICON[currentResult ?? ""] ?? Ruler;
                        return <Icon className="h-[18px] w-[18px]" strokeWidth={2} />;
                      })()}
                    </span>
                    <h3 className="text-[15px] font-bold text-stone-900">计算结果</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-px bg-stone-100 sm:grid-cols-3 lg:grid-cols-5">
                    {cur.results.map((f) => (
                      <div key={f.key} className="bg-white px-5 py-4">
                        <p className="mb-1.5 truncate text-[11px] font-medium text-stone-400">{f.label}</p>
                        <p className="text-lg font-extrabold tracking-tight tabular-nums text-stone-900">
                          {formatVal(f.value)}
                          {f.unit && <span className="ml-1.5 text-xs font-medium text-stone-400">{f.unit}</span>}
                        </p>
                      </div>
                    ))}
                  </div>
                  {cur.plots?.main && (
                    <div className="border-t border-stone-100 bg-stone-50/40 p-5 sm:p-6">
                      <div className="flex justify-center rounded-xl border border-stone-200/70 bg-white p-3 sm:p-5">
                        <img
                          src={`data:image/png;base64,${cur.plots.main}`}
                          alt={`${spec.name} 拟合图像`}
                          className="max-h-[440px] w-auto object-contain"
                        />
                      </div>
                    </div>
                  )}
                  {currentResult && processed[currentResult] && (
                    <DataEcho
                      methodId={currentResult}
                      rowsPayload={processed[currentResult].rows}
                    />
                  )}
                </div>
              </>
            ) : (
              <p className="py-16 text-center text-stone-400">还没有计算结果</p>
            )}

            {/* deliverables */}
            {processedKeys.length > 0 && (
              <div className="card mt-6 overflow-hidden shadow-soft">
                <div className="flex items-center gap-3 border-b border-stone-100 bg-stone-50/60 px-6 py-4">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25">
                    <FileDown className="h-[18px] w-[18px]" strokeWidth={2} />
                  </span>
                  <div>
                    <h3 className="text-[15px] font-bold text-stone-900">报告交付文件</h3>
                    <p className="text-xs text-stone-400">
                      一份完整报告：表格 → 图片 → 详细数据处理 → 拓展、建议、误差分析与总结
                    </p>
                  </div>
                </div>
                <div className="p-5 sm:p-6">
                  <div
                    className={cn(
                      "flex flex-col justify-between gap-3 rounded-xl border p-4",
                      basicReady
                        ? "border-stone-200/80"
                        : "border-dashed border-amber-200 bg-amber-50/40"
                    )}
                  >
                    <div>
                      <p className="text-sm font-bold text-stone-900">完整实验报告</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-stone-400">
                        A4 纵向紧凑排版，四部分强制分页；表格整表保留，公式以 LaTeX 风格展示
                      </p>
                      {!basicReady && (
                        <p className="mt-1.5 text-xs font-semibold text-amber-600">
                          完成必做方法计算后可生成：{missingRequired.join("、")}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          runDownload("report-docx", () => downloadSoundLightReport("docx", reportData))
                        }
                        disabled={busyKey !== null || !basicReady}
                        className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-stone-900 text-xs font-semibold text-white transition-colors hover:bg-stone-700 disabled:opacity-50"
                      >
                        {busyKey === "report-docx" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                        Word 版
                      </button>
                      <button
                        onClick={() =>
                          runDownload("report-pdf", () => downloadSoundLightReport("pdf", reportData))
                        }
                        disabled={busyKey !== null || !basicReady}
                        className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {busyKey === "report-pdf" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                        紧凑 PDF
                      </button>
                    </div>
                  </div>
                </div>
                {dlError && (
                  <p className="px-6 pb-4 text-xs font-medium text-red-500" role="alert">
                    {dlError}
                  </p>
                )}
              </div>
            )}

            <div className="mt-8 flex items-center justify-center gap-3">
              <button
                onClick={() => setStep("input")}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-6 text-sm font-semibold text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-900"
              >
                <ArrowLeft className="h-4 w-4" /> 返回录入
              </button>
              <Link
                href="/experiments/sound-light"
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-stone-900 px-6 text-sm font-semibold text-white shadow-md transition-all hover:-translate-y-0.5 hover:bg-stone-700"
              >
                返回实验详情 <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function formatVal(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (Number.isInteger(n)) return n.toString();
  if (abs >= 1e5) return n.toExponential(4).replace("e+", "×10^").replace("e-", "×10^-");
  if (abs >= 100) return n.toFixed(1);
  if (abs >= 1) return n.toFixed(3);
  return n.toFixed(4);
}
