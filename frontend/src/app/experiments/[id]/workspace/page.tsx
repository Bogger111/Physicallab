"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  Table2,
  ClipboardList,
  ChartSpline,
  ChartLine,
  Sigma,
  Waves,
  Orbit,
  Download,
  FileDown,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Eye,
  ChevronRight,
  ListChecks,
} from "lucide-react";
import { getExperiment } from "@/lib/experiments";
import {
  processPolarization,
  downloadRecordSheet,
  previewRecordSheet,
  downloadReport,
  type ProcessRequest,
  type ProcessResponse,
} from "@/lib/api";
import DataInputTable from "@/components/workspace/DataInputTable";
import SoundLightWorkspace from "@/components/workspace/SoundLightWorkspace";
import { cn } from "@/lib/utils";

type Step = "record" | "input" | "confirm" | "results";

const STEPS: { id: Step; label: string; icon: React.ElementType }[] = [
  { id: "record", label: "数据记录表", icon: FileText },
  { id: "input", label: "录入数据", icon: Table2 },
  { id: "confirm", label: "确认数据", icon: ClipboardList },
  { id: "results", label: "结果", icon: ChartSpline },
];

const SUB_ICON: Record<string, React.ElementType> = {
  malus: ChartLine,
  halfwave: Sigma,
  quarterwave: Waves,
  circular: Orbit,
};

function PolarizationWorkspace({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const experiment = getExperiment(id);

  const [step, setStep] = useState<Step>("record");
  const [activeTab, setActiveTab] = useState("malus");

  // Setup
  const [bgUw, setBgUw] = useState("0.0543");
  const [thetaQwp, setThetaQwp] = useState("30");

  // Malus data: 90,80,...,0
  const [malusData, setMalusData] = useState<string[][]>(
    Array.from({ length: 10 }, (_, i) => [String(90 - i * 10), "", ""])
  );

  // HalfWave initial
  const [hwInit, setHwInit] = useState({
    c_deg: "",
    c_min: "",
    p2_deg: "",
    p2_min: "",
  });
  // HalfWave rows
  const [hwData, setHwData] = useState<string[][]>(
    Array.from({ length: 6 }, (_, i) => [String(i * 10), "", "", "", ""])
  );

  // QuarterWave: 36 rows
  const [qwData, setQwData] = useState<string[][]>(
    Array.from({ length: 36 }, (_, i) => [String(i * 10), ""])
  );

  // Circular: 36 rows
  const [circData, setCircData] = useState<string[][]>(
    Array.from({ length: 36 }, (_, i) => [String(i * 10), ""])
  );

  // Results
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);

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

  const buildRequest = useCallback((): ProcessRequest => {
    return {
      bg_uw: parseFloat(bgUw) || 0,
      theta_qwp: parseFloat(thetaQwp) || 30,
      malus: {
        rows: malusData.map((r) => ({
          theta: parseFloat(r[0]) || 0,
          i_left: r[1] ? parseFloat(r[1]) : null,
          i_right: r[2] ? parseFloat(r[2]) : null,
        })),
      },
      halfwave: {
        initial: {
          c_deg: parseFloat(hwInit.c_deg) || 0,
          c_min: parseFloat(hwInit.c_min) || 0,
          p2_deg: parseFloat(hwInit.p2_deg) || 0,
          p2_min: parseFloat(hwInit.p2_min) || 0,
        },
        rows: hwData.map((r) => ({
          offset: parseFloat(r[0]) || 0,
          c_deg: parseFloat(r[1]) || 0,
          c_min: parseFloat(r[2]) || 0,
          p2_deg: parseFloat(r[3]) || 0,
          p2_min: parseFloat(r[4]) || 0,
        })),
      },
      quarterwave: {
        rows: qwData.map((r) => ({
          phi: parseFloat(r[0]) || 0,
          i_raw: r[1] ? parseFloat(r[1]) : null,
        })),
      },
      circular: {
        rows: circData.map((r) => ({
          angle: parseFloat(r[0]) || 0,
          i_raw: r[1] ? parseFloat(r[1]) : null,
        })),
      },
    };
  }, [bgUw, thetaQwp, malusData, hwInit, hwData, qwData, circData]);

  // ---- derived fill stats (same per-sub heuristics as submission) ----
  const fills = {
    malus: malusData.filter((r) => r[1] || r[2]).length,
    halfwave: hwData.filter((r) => r[1] && r[3]).length,
    quarterwave: qwData.filter((r) => r[1]).length,
    circular: circData.filter((r) => r[1]).length,
  };
  const totals = { malus: 10, halfwave: 6, quarterwave: 36, circular: 36 };
  const filledSum = Object.values(fills).reduce((a, b) => a + b, 0);
  const totalSum = Object.values(totals).reduce((a, b) => a + b, 0);

  if (!experiment) {
    return (
      <div className="container-x py-24 text-center">
        <p className="font-semibold text-stone-500">实验未找到</p>
        <Link href="/experiments" className="mt-3 inline-block text-sm text-indigo-600">
          返回实验库
        </Link>
      </div>
    );
  }

  const currentStepIndex = STEPS.findIndex((s) => s.id === step);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    try {
      const req = buildRequest();
      const res = await processPolarization(req);
      if (res.status === "validation_error") {
        setError(res.errors?.join("；") || "数据校验失败");
        return;
      }
      if (res.status === "calculation_error") {
        setError(res.error || "计算过程出错");
        return;
      }
      setResult(res);
      setStep("results");
    } catch {
      setError("网络错误，请确认后端服务已启动 (http://localhost:8000)");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
    setStep("input");
  };

  const downloadPlot = (plotKey: string) => {
    if (!result?.plots[plotKey]) return;
    const link = document.createElement("a");
    link.href = `data:image/png;base64,${result.plots[plotKey]}`;
    link.download = `${experiment.id}_${plotKey}.png`;
    link.click();
  };

  const downloadAllPlots = () => {
    if (!result?.plots) return;
    Object.keys(result.plots).forEach((key) => downloadPlot(key));
  };

  const plotCount = result ? Object.keys(result.plots).length : 0;

  return (
    <div className="min-h-screen">
      {/* ===== Top bar ===== */}
      <div className="border-b border-stone-200/70 bg-white">
        <div className="container-x flex h-14 items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href={`/experiments/${id}`}
              className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-[13px] font-medium text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-800"
            >
              <ArrowLeft className="h-4 w-4" />
              返回
            </Link>
            <span aria-hidden className="h-4 w-px shrink-0 bg-stone-200" />
            <div className="flex min-w-0 items-baseline gap-2">
              <h1 className="truncate text-sm font-bold text-stone-900">{experiment.name}</h1>
              <span className="hidden shrink-0 text-xs font-medium text-stone-400 sm:inline">
                数据处理工作台
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {step === "results" && result?.status === "success" && (
              <button
                onClick={downloadAllPlots}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-600/25 transition-colors hover:bg-indigo-700"
              >
                <Download className="h-3.5 w-3.5" />
                导出全部
                <span className="rounded bg-white/20 px-1 text-[11px] tabular-nums">{plotCount}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ===== Stepper ===== */}
      <div className="border-b border-stone-200/60 bg-white/70 backdrop-blur">
        <div className="container-x flex items-center py-4">
          {STEPS.map((s, i) => {
            const isActive = s.id === step;
            const isCompleted = i < currentStepIndex;
            const Icon = s.icon;
            return (
              <div key={s.id} className={cn("flex items-center", i > 0 && "flex-1")}>
                {i > 0 && (
                  <div className="relative mx-3 h-[2px] flex-1 overflow-hidden rounded-full bg-stone-200 sm:mx-4">
                    {isCompleted && (
                      <div className="absolute inset-0 origin-left rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" />
                    )}
                  </div>
                )}
                <button
                  onClick={() => {
                    if (isCompleted) setStep(s.id);
                  }}
                  disabled={!isCompleted && !isActive}
                  aria-current={isActive ? "step" : undefined}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-full transition-colors",
                    (isCompleted || isActive) && "cursor-pointer"
                  )}
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

      {/* ===== Content ===== */}
      <div className="container-x py-8 sm:py-10">
        {/* ---------- STEP 1 · record ---------- */}
        {step === "record" && (
          <div className="mx-auto max-w-xl animate-rise-in">
            <div className="mb-7 text-center">
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.24em] text-indigo-500">
                Step 01 · 数据记录表
              </p>
              <h2 className="text-2xl font-extrabold tracking-tight text-stone-900">
                进实验室前，先打印这张表
              </h2>
              <p className="mx-auto mt-2.5 max-w-md text-sm leading-relaxed text-stone-500">
                下载标准记录表并打印，实验时按表格逐格手写读数，回来即可快速录入。
              </p>
            </div>

            <div className="card p-7 text-center shadow-soft sm:p-9">
              <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 shadow-lg shadow-indigo-600/30">
                <FileText className="h-10 w-10 text-white" strokeWidth={1.8} />
              </div>
              <p className="text-lg font-bold text-stone-900">
                {experiment.name} · 数据记录表
              </p>
              <p className="mt-1.5 text-sm text-stone-400">PDF · A4 打印版</p>

              <ul className="mx-auto mt-6 flex max-w-xs flex-col gap-2.5 text-left">
                {experiment.subExperiments.map((s, i) => (
                  <li key={s.id} className="flex items-center gap-2.5 text-sm text-stone-600">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-indigo-50 font-mono text-[10px] font-bold text-indigo-600">
                      {i + 1}
                    </span>
                    {s.name}
                    <span className="ml-auto text-xs tabular-nums text-stone-400">
                      {s.resultFields.length} 项结果
                    </span>
                  </li>
                ))}
              </ul>

              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <button
                  onClick={() => runDownload("preview", previewRecordSheet)}
                  disabled={busyKey !== null}
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-stone-300 bg-white px-5 text-sm font-semibold text-stone-700 transition-colors hover:border-stone-400 hover:bg-stone-50 disabled:opacity-50"
                >
                  <Eye className="h-4 w-4" />
                  预览
                </button>
                <button
                  onClick={() => runDownload("record-docx", () => downloadRecordSheet("docx"))}
                  disabled={busyKey !== null}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-stone-900 px-5 text-sm font-semibold text-white shadow-md transition-all hover:-translate-y-0.5 hover:bg-stone-700 disabled:opacity-50"
                >
                  {busyKey === "record-docx" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileDown className="h-4 w-4" />
                  )}
                  下载 Word
                </button>
                <button
                  onClick={() => runDownload("record-pdf", () => downloadRecordSheet("pdf"))}
                  disabled={busyKey !== null}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-indigo-600 px-5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-700 disabled:opacity-50"
                >
                  {busyKey === "record-pdf" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  下载 PDF
                </button>
              </div>
              {dlError && (
                <p className="mt-3 text-center text-xs font-medium text-red-500" role="alert">
                  {dlError}
                </p>
              )}
            </div>

            <button
              onClick={() => setStep("input")}
              className="group mt-7 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-stone-900 text-[15px] font-semibold text-white shadow-lg shadow-stone-900/20 transition-all hover:-translate-y-0.5 hover:bg-stone-800"
            >
              打印好了，开始录入数据
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          </div>
        )}

        {/* ---------- STEP 2 · input ---------- */}
        {step === "input" && (
          <div className="mx-auto max-w-5xl animate-rise-in">
            <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.24em] text-indigo-500">
                  Step 02 · 录入数据
                </p>
                <h2 className="text-2xl font-extrabold tracking-tight text-stone-900">
                  把纸质读数逐格敲进来
                </h2>
              </div>
              <p className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-400">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-stone-100 text-stone-500">
                  <ListChecks className="h-3.5 w-3.5" />
                </span>
                已录入 {filledSum}/{totalSum} 组
              </p>
            </div>

            {/* Setup params */}
            <div className="card mb-6 flex flex-col gap-5 p-6 shadow-soft sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-[15px] font-bold text-stone-900">实验参数设置</h3>
                <p className="mt-0.5 text-xs text-stone-400">整场实验共用的条件参数</p>
              </div>
              <div className="flex flex-wrap gap-4 sm:gap-6">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-stone-500">背景光强 I₀</span>
                  <span className="relative inline-flex items-center">
                    <input
                      type="number"
                      step="any"
                      value={bgUw}
                      onChange={(e) => setBgUw(e.target.value)}
                      className="h-9 w-28 rounded-lg border border-stone-200 bg-white px-3 pr-9 text-right text-sm font-medium tabular-nums text-stone-800 shadow-sm outline-none transition-all focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                    />
                    <span className="pointer-events-none absolute right-3 text-xs text-stone-400">
                      μW
                    </span>
                  </span>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-stone-500">1/4 波片快轴 θ_qwp</span>
                  <select
                    value={thetaQwp}
                    onChange={(e) => setThetaQwp(e.target.value)}
                    className="h-9 w-28 rounded-lg border border-stone-200 bg-white px-3 text-sm font-medium text-stone-800 shadow-sm outline-none transition-all focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                  >
                    <option value="30">30°</option>
                    <option value="60">60°</option>
                  </select>
                </label>
              </div>
            </div>

            {/* Sub-experiment tabs */}
            <div className="mb-2 flex items-center justify-between gap-4 overflow-x-auto">
              <div className="flex gap-1" role="tablist" aria-label="子实验数据">
                {experiment.subExperiments.map((sub) => {
                  const isActive = activeTab === sub.id;
                  return (
                    <button
                      key={sub.id}
                      role="tab"
                      aria-selected={isActive}
                      onClick={() => setActiveTab(sub.id)}
                      className={cn(
                        "relative flex items-center gap-1.5 whitespace-nowrap px-4 py-2.5 text-sm transition-colors",
                        isActive
                          ? "font-bold text-stone-900"
                          : "font-medium text-stone-400 hover:text-stone-600"
                      )}
                    >
                      {sub.name}
                      {sub.required && (
                        <span
                          className={cn(
                            "text-[11px] font-bold",
                            isActive ? "text-red-500" : "text-stone-300"
                          )}
                        >
                          必
                        </span>
                      )}
                      {isActive && (
                        <span className="absolute inset-x-2 bottom-0 h-[2.5px] rounded-full bg-gradient-to-r from-indigo-600 to-violet-600" />
                      )}
                    </button>
                  );
                })}
              </div>
              <span className="hidden shrink-0 text-[11px] text-stone-300 md:inline">
                Tab / Enter 切换单元格 · 支持整列粘贴
              </span>
            </div>

            {/* Tab panels */}
            {activeTab === "malus" && (
              <div className="animate-fade-in">
                <p className="mb-3 rounded-xl bg-indigo-50/80 px-4 py-2.5 text-[13px] leading-relaxed text-indigo-900/80 ring-1 ring-inset ring-indigo-100">
                  θ 从 <b>90°（消光）</b>到 <b>0°</b>，每 10° 记录左右旋光强 I 左 / I 右（μW）。
                </p>
                <DataInputTable
                  headers={[
                    { label: "θ (°)", readOnly: true },
                    { label: "I 左旋 (μW)" },
                    { label: "I 右旋 (μW)" },
                  ]}
                  data={malusData}
                  onChange={setMalusData}
                />
              </div>
            )}

            {activeTab === "halfwave" && (
              <div className="animate-fade-in">
                <div className="card mb-3 p-5">
                  <h4 className="mb-4 flex items-center gap-2 text-[13px] font-bold text-stone-700">
                    <Sigma className="h-4 w-4 text-indigo-600" />
                    初始读数（度 + 分）
                  </h4>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    {[
                      { key: "c_deg", label: "C 初始 · 度" },
                      { key: "c_min", label: "C 初始 · 分" },
                      { key: "p2_deg", label: "P2 初始 · 度" },
                      { key: "p2_min", label: "P2 初始 · 分" },
                    ].map((f) => (
                      <label key={f.key} className="flex flex-col gap-1.5">
                        <span className="text-xs font-medium text-stone-400">{f.label}</span>
                        <input
                          type="number"
                          value={hwInit[f.key as keyof typeof hwInit]}
                          onChange={(e) =>
                            setHwInit((prev) => ({ ...prev, [f.key]: e.target.value }))
                          }
                          className="h-9 rounded-lg border border-stone-200 bg-white px-3 text-sm font-medium tabular-nums text-stone-800 shadow-sm outline-none transition-all focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                        />
                      </label>
                    ))}
                  </div>
                </div>
                <p className="mb-3 rounded-xl bg-indigo-50/80 px-4 py-2.5 text-[13px] leading-relaxed text-indigo-900/80 ring-1 ring-inset ring-indigo-100">
                  每次 C 旋转 <b>10°</b>，记录 C 与 P2 刻度盘的度、分读数，共 6 组。
                </p>
                <DataInputTable
                  headers={[
                    { label: "序号", readOnly: true },
                    { label: "C (度)" },
                    { label: "C (分)" },
                    { label: "P2 (度)" },
                    { label: "P2 (分)" },
                  ]}
                  data={hwData}
                  onChange={setHwData}
                />
              </div>
            )}

            {activeTab === "quarterwave" && (
              <div className="animate-fade-in">
                <p className="mb-3 rounded-xl bg-indigo-50/80 px-4 py-2.5 text-[13px] leading-relaxed text-indigo-900/80 ring-1 ring-inset ring-indigo-100">
                  P2 每转 <b>10°</b> 记一次光强，φ 从 0° 到 350° 共 <b>36</b> 个数据点。
                </p>
                <DataInputTable
                  headers={[
                    { label: "φ (°)", readOnly: true },
                    { label: "I (μW)" },
                  ]}
                  data={qwData}
                  onChange={setQwData}
                  compact
                />
              </div>
            )}

            {activeTab === "circular" && (
              <div className="animate-fade-in">
                <p className="mb-3 rounded-xl bg-indigo-50/80 px-4 py-2.5 text-[13px] leading-relaxed text-indigo-900/80 ring-1 ring-inset ring-indigo-100">
                  圆偏振光通过检偏器，P2 每转 <b>10°</b> 记录光强，共 <b>36</b> 点。
                </p>
                <DataInputTable
                  headers={[
                    { label: "P2 (°)", readOnly: true },
                    { label: "I (μW)" },
                  ]}
                  data={circData}
                  onChange={setCircData}
                  compact
                />
              </div>
            )}

            {error && (
              <div
                role="alert"
                className="mt-5 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-relaxed text-red-700"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Actions */}
            <div className="mt-8 flex flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center">
              <button
                onClick={() => setStep("record")}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-5 text-sm font-semibold text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-900 sm:justify-start"
              >
                <ArrowLeft className="h-4 w-4" />
                上一步
              </button>
              <button
                onClick={() => {
                  setError(null);
                  setStep("confirm");
                }}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-7 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-700"
              >
                确认数据
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* ---------- STEP 3 · confirm ---------- */}
        {step === "confirm" && (
          <div className="mx-auto max-w-3xl animate-rise-in">
            <div className="mb-7 text-center">
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.24em] text-indigo-500">
                Step 03 · 确认数据
              </p>
              <h2 className="text-2xl font-extrabold tracking-tight text-stone-900">
                核对无误后，开始计算
              </h2>
              <p className="mx-auto mt-2.5 max-w-md text-sm leading-relaxed text-stone-500">
                请对照纸质记录表逐项检查。带「必」的模块若为空，计算会被拒绝。
              </p>
            </div>

            <div className="card mb-5 flex items-center justify-between gap-4 px-6 py-4">
              <span className="shrink-0 text-sm font-semibold text-stone-600">整体进度</span>
              <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
                <div className="h-2 w-full max-w-56 overflow-hidden rounded-full bg-stone-200/70">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      filledSum === totalSum
                        ? "bg-gradient-to-r from-emerald-500 to-teal-500"
                        : "bg-gradient-to-r from-indigo-500 to-violet-500"
                    )}
                    style={{ width: `${Math.round((filledSum / totalSum) * 100)}%` }}
                  />
                </div>
                <span className="shrink-0 text-sm font-extrabold tabular-nums text-stone-900">
                  {filledSum}
                  <span className="mx-0.5 font-medium text-stone-300">/</span>
                  {totalSum}
                </span>
                <span className="shrink-0 text-xs text-stone-400">组读数</span>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {experiment.subExperiments.map((sub) => {
                const filled = fills[sub.id as keyof typeof fills];
                const total = totals[sub.id as keyof typeof totals];
                const pct = total ? Math.round((filled / total) * 100) : 0;
                const done = filled === total;
                const none = filled === 0;
                const state = done ? "done" : none ? (sub.required ? "empty" : "idle") : "partial";
                const Icon = SUB_ICON[sub.id] ?? Table2;
                return (
                  <div
                    key={sub.id}
                    className={cn(
                      "card p-5 transition-shadow hover:shadow-soft",
                      state === "empty" && "border-red-200"
                    )}
                  >
                    <div className="mb-4 flex items-start gap-3.5">
                      <span
                        className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                          state === "done" && "bg-emerald-50 text-emerald-600",
                          state === "partial" && "bg-amber-50 text-amber-600",
                          state === "empty" && "bg-red-50 text-red-500",
                          state === "idle" && "bg-stone-100 text-stone-400"
                        )}
                      >
                        <Icon className="h-5 w-5" strokeWidth={1.9} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-[15px] font-bold text-stone-900">{sub.name}</p>
                          {sub.required ? (
                            <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600">
                              必
                            </span>
                          ) : (
                            <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-bold text-stone-400">
                              选
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 line-clamp-1 text-xs text-stone-400">{sub.description}</p>
                      </div>
                    </div>

                    <div className="mb-2.5 flex items-center justify-between gap-2">
                      <span
                        className={cn(
                          "inline-flex items-center text-xs font-semibold",
                          state === "done" && "text-emerald-600",
                          state === "partial" && "text-amber-600",
                          state === "empty" && sub.required && "text-red-500",
                          (state === "idle" || (state === "empty" && !sub.required)) &&
                            "text-stone-400"
                        )}
                      >
                        {state === "done" && (
                          <>
                            已录完
                            <CheckCircle2 className="ml-1 h-3.5 w-3.5" />
                          </>
                        )}
                        {state === "partial" && `已录入 ${filled}/${total}`}
                        {state === "empty" && sub.required && "未填写 · 必做"}
                        {state === "empty" && !sub.required && "未填写 · 可跳过"}
                        {state === "idle" && "未填写 · 可跳过"}
                      </span>
                      <span className="text-[11px] font-medium tabular-nums text-stone-400">
                        {filled}/{total}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-stone-200/60">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-300",
                          state === "done" && "bg-emerald-500",
                          state === "partial" && "bg-amber-400",
                          state === "empty" && "bg-red-300",
                          state === "idle" && "bg-stone-200"
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
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

            <div className="mt-8 flex flex-col-reverse items-stretch justify-center gap-3 sm:flex-row sm:items-center">
              <button
                onClick={() => setStep("input")}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-6 text-sm font-semibold text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-900 sm:justify-start"
              >
                <ArrowLeft className="h-4 w-4" />
                返回修改
              </button>
              <button
                onClick={handleProcess}
                disabled={loading}
                className="group inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-8 text-[15px] font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在计算…
                  </>
                ) : (
                  <>
                    生成实验结果
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ---------- STEP 4 · results ---------- */}
        {step === "results" && result?.status === "success" && (
          <div className="mx-auto max-w-5xl animate-rise-in">
            <div className="mb-8 flex flex-col items-start justify-between gap-4 rounded-2xl border border-emerald-200/70 bg-gradient-to-r from-emerald-50 via-white to-emerald-50/50 p-6 sm:flex-row sm:items-center">
              <div className="flex items-center gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/30">
                  <CheckCircle2 className="h-6 w-6" />
                </span>
                <div>
                  <p className="text-lg font-extrabold tracking-tight text-stone-900">
                    数据处理完成
                  </p>
                  <p className="mt-0.5 text-sm text-stone-500">
                    4 个子实验 · {plotCount} 张拟合图，可逐张下载或一键导出
                  </p>
                </div>
              </div>
              <button
                onClick={downloadAllPlots}
                className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl bg-stone-900 px-5 text-sm font-semibold text-white shadow-md transition-all hover:-translate-y-0.5 hover:bg-stone-700"
              >
                <Download className="h-4 w-4" />
                导出全部图像
              </button>
            </div>

            {/* Deliverables: Word + compact PDF per part */}
            <div className="card mb-8 overflow-hidden shadow-soft">
              <div className="flex items-center justify-between border-b border-stone-100 bg-stone-50/60 px-6 py-4">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25">
                    <FileDown className="h-[18px] w-[18px]" strokeWidth={2} />
                  </span>
                  <div>
                    <h3 className="text-[15px] font-bold text-stone-900">报告交付文件</h3>
                    <p className="text-xs text-stone-400">
                      每个部分 = 可编辑 Word + 紧凑排版 PDF（表格无底色，省纸打印）
                    </p>
                  </div>
                </div>
              </div>
              <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
                {[
                  {
                    part: "basic" as const,
                    name: "基准报告",
                    desc: "数据表 + 计算结果 + 4 张基准图（含 I 左/右对比）",
                  },
                  {
                    part: "advanced" as const,
                    name: "拓展报告",
                    desc: "残差 / 理论对比 / 恒定性 / 参数汇总等误差分析图",
                  },
                ].map((item) => (
                  <div
                    key={item.part}
                    className="flex flex-col justify-between gap-3 rounded-xl border border-stone-200/80 p-4"
                  >
                    <div>
                      <p className="text-sm font-bold text-stone-900">
                        报告 · {item.name}
                      </p>
                      <p className="mt-0.5 text-xs leading-relaxed text-stone-400">{item.desc}</p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          runDownload(
                            `${item.part}-docx`,
                            () => downloadReport(item.part, "docx", buildRequest())
                          )
                        }
                        disabled={busyKey !== null}
                        className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-stone-900 text-xs font-semibold text-white transition-colors hover:bg-stone-700 disabled:opacity-50"
                      >
                        {busyKey === `${item.part}-docx` ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <FileText className="h-3.5 w-3.5" />
                        )}
                        Word 版
                      </button>
                      <button
                        onClick={() =>
                          runDownload(
                            `${item.part}-pdf`,
                            () => downloadReport(item.part, "pdf", buildRequest())
                          )
                        }
                        disabled={busyKey !== null}
                        className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {busyKey === `${item.part}-pdf` ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="h-3.5 w-3.5" />
                        )}
                        紧凑 PDF
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {dlError && (
                <p className="px-6 pb-4 text-xs font-medium text-red-500" role="alert">
                  {dlError}
                </p>
              )}
            </div>

            <div className="space-y-6">
              {experiment.subExperiments.map((sub) => {
                const subResult = result.results[sub.id];
                if (!subResult) return null;
                const plotKey = sub.id;
                const plotData = result.plots[plotKey];
                const Icon = SUB_ICON[sub.id] ?? Table2;

                return (
                  <div key={sub.id} className="card overflow-hidden shadow-soft">
                    {/* header */}
                    <div className="flex items-center gap-3 border-b border-stone-100 bg-stone-50/60 px-6 py-4">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25">
                        <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-[15px] font-bold text-stone-900">{sub.name}</h3>
                        <p className="truncate text-xs text-stone-400">{sub.description}</p>
                      </div>
                      {plotData && (
                        <button
                          onClick={() => downloadPlot(plotKey)}
                          className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs font-semibold text-stone-500 transition-colors hover:border-stone-300 hover:text-stone-800"
                        >
                          <FileDown className="h-3.5 w-3.5" />
                          下载 PNG
                        </button>
                      )}
                    </div>

                    {/* metrics */}
                    <div className="grid grid-cols-2 gap-px bg-stone-100 sm:grid-cols-3 xl:grid-cols-5">
                      {sub.resultFields.map((field) => (
                        <div key={field.key} className="bg-white px-5 py-4">
                          <p className="mb-1.5 truncate text-[11px] font-medium text-stone-400">
                            {field.label}
                          </p>
                          <p className="text-lg font-extrabold tracking-tight tabular-nums text-stone-900">
                            {typeof subResult[field.key] === "number"
                              ? formatNumber(subResult[field.key])
                              : (subResult[field.key] ?? "—")}
                            {field.unit && (
                              <span className="ml-1.5 text-xs font-medium text-stone-400">
                                {field.unit}
                              </span>
                            )}
                          </p>
                        </div>
                      ))}
                    </div>

                    {/* plot */}
                    {plotData && (
                      <div className="border-t border-stone-100 bg-stone-50/40 p-5 sm:p-6">
                        <div className="flex justify-center rounded-xl border border-stone-200/70 bg-white p-3 sm:p-5">
                          <img
                            src={`data:image/png;base64,${plotData}`}
                            alt={`${sub.name} 拟合图像`}
                            className="max-h-[420px] w-auto object-contain"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <button
                onClick={handleReset}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-6 text-sm font-semibold text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-900 sm:w-auto"
              >
                <RefreshCw className="h-4 w-4" />
                重新修改数据
              </button>
              <Link
                href="/experiments"
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-7 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-700 sm:w-auto"
              >
                返回实验库
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function formatNumber(n: number): string {
  if (Number.isInteger(n)) return n.toString();
  if (Math.abs(n) >= 100) return n.toFixed(2);
  if (Math.abs(n) >= 1) return n.toFixed(4);
  if (Math.abs(n) >= 0.01) return n.toFixed(4);
  return n.toExponential(4);
}

// Route dispatch: sound-light uses its own workspace; everything else falls
// back to the polarization-style guided workspace.
export default function ExperimentWorkspaceRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  if (id === "sound-light") {
    return <SoundLightWorkspace />;
  }
  return <PolarizationWorkspace params={params} />;
}
