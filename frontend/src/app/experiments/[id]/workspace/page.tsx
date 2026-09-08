"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Table2,
  CheckCircle2,
  BarChart3,
  Download,
  RefreshCw,
  Loader2,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { getExperiment, type ExperimentConfig } from "@/lib/experiments";
import { processPolarization, type ProcessRequest, type ProcessResponse } from "@/lib/api";
import DataInputTable from "@/components/workspace/DataInputTable";

type Step = "record" | "input" | "confirm" | "results";

const STEPS: { id: Step; label: string; icon: React.ElementType }[] = [
  { id: "record", label: "数据记录", icon: FileText },
  { id: "input", label: "数据录入", icon: Table2 },
  { id: "confirm", label: "数据确认", icon: CheckCircle2 },
  { id: "results", label: "结果", icon: BarChart3 },
];

export default function WorkspacePage({
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
    Array.from({ length: 10 }, (_, i) => [
      String(90 - i * 10),
      "",
      "",
    ])
  );

  // HalfWave initial
  const [hwInit, setHwInit] = useState({ c_deg: "", c_min: "", p2_deg: "", p2_min: "" });
  // HalfWave rows
  const [hwData, setHwData] = useState<string[][]>(
    Array.from({ length: 6 }, (_, i) => [
      String(i * 10),
      "",
      "",
      "",
      "",
    ])
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

  if (!experiment) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-20 text-center">
        <p className="text-gray-400">实验未找到</p>
      </div>
    );
  }

  const currentStepIndex = STEPS.findIndex((s) => s.id === step);

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

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    try {
      const req = buildRequest();
      const res = await processPolarization(req);
      if (res.status === "validation_error") {
        setError(res.errors?.join("；") || "数据校验失败");
        setLoading(false);
        return;
      }
      if (res.status === "calculation_error") {
        setError(res.error || "计算过程出错");
        setLoading(false);
        return;
      }
      setResult(res);
      setStep("results");
    } catch (e) {
      setError("网络错误，请确认后端服务已启动 (http://localhost:8000)");
    }
    setLoading(false);
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

  return (
    <div className="animate-in min-h-[calc(100vh-4rem)]">
      {/* Top Bar */}
      <div className="border-b border-gray-100 bg-white">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link
              href={`/experiments/${id}`}
              className="flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-gray-700"
            >
              <ArrowLeft className="h-4 w-4" />
              返回
            </Link>
            <div className="h-4 w-px bg-gray-200" />
            <span className="text-sm font-semibold text-gray-900">{experiment.name}</span>
          </div>
          {step === "results" && result?.status === "success" && (
            <button
              onClick={downloadAllPlots}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-700"
            >
              <Download className="h-3.5 w-3.5" />
              导出全部
            </button>
          )}
        </div>
      </div>

      {/* Stepper */}
      <div className="border-b border-gray-100 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-1 px-6 py-3">
          {STEPS.map((s, i) => {
            const isActive = s.id === step;
            const isCompleted = i < currentStepIndex;
            const Icon = s.icon;
            return (
              <div key={s.id} className="flex items-center">
                <button
                  onClick={() => {
                    if (isCompleted) setStep(s.id);
                  }}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : isCompleted
                      ? "text-green-600 cursor-pointer hover:bg-gray-50"
                      : "text-gray-300 cursor-default"
                  }`}
                  disabled={!isCompleted && !isActive}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{s.label}</span>
                </button>
                {i < STEPS.length - 1 && (
                  <ChevronRight className="mx-1 h-4 w-4 text-gray-200" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-4xl px-6 py-8">
        {/* Step 1: Record Sheet */}
        {step === "record" && (
          <div className="animate-in mx-auto max-w-2xl">
            <div className="mb-8 text-center">
              <h2 className="mb-2 text-xl font-semibold">实验数据记录表</h2>
              <p className="text-sm text-gray-400">
                实验前请下载并打印标准数据记录表
              </p>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-white p-8">
              <div className="mb-6 flex items-center justify-center">
                <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-blue-50">
                  <FileText className="h-10 w-10 text-blue-600" />
                </div>
              </div>
              <p className="mb-6 text-center text-sm text-gray-400">
                标准 A4 排版，包含全部子实验的数据表格。
                <br />
                打印后带入实验室，按表格格式手写记录数据。
              </p>
              <div className="flex justify-center gap-3">
                <a
                  href={experiment.recordSheet}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-100 bg-white px-5 text-sm font-medium transition-colors hover:bg-gray-50"
                >
                  预览记录表
                </a>
                <a
                  href={experiment.recordSheet}
                  download
                  className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Download className="h-4 w-4" />
                  下载 PDF
                </a>
              </div>
            </div>
            <div className="mt-8 text-center">
              <button
                onClick={() => setStep("input")}
                className="inline-flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-8 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                下一步：录入数据
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Data Input */}
        {step === "input" && (
          <div className="animate-in">
            {/* Setup */}
            <div className="mb-6 rounded-2xl border border-gray-100 bg-white p-7">
              <h3 className="mb-3 text-sm font-semibold">实验参数设置</h3>
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <span className="text-gray-400">背景光强</span>
                  <input
                    type="number"
                    step="any"
                    value={bgUw}
                    onChange={(e) => setBgUw(e.target.value)}
                    className="h-8 w-24 rounded-md border border-border px-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/20"
                  />
                  <span className="text-xs text-gray-400">μW</span>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <span className="text-gray-400">θ_qwp</span>
                  <select
                    value={thetaQwp}
                    onChange={(e) => setThetaQwp(e.target.value)}
                    className="h-8 rounded-md border border-border px-2 text-sm outline-none focus:border-primary"
                  >
                    <option value="30">30°</option>
                    <option value="60">60°</option>
                  </select>
                </label>
              </div>
            </div>

            {/* Sub-experiment tabs */}
            <div className="mb-4 flex gap-1 overflow-x-auto border-b border-border">
              {experiment.subExperiments.map((sub) => (
                <button
                  key={sub.id}
                  onClick={() => setActiveTab(sub.id)}
                  className={`relative whitespace-nowrap px-4 py-2.5 text-sm transition-colors ${
                    activeTab === sub.id
                      ? "text-primary font-medium"
                      : "text-gray-400 hover:text-foreground"
                  }`}
                >
                  {sub.name}
                  {sub.required && (
                    <span className="ml-1 text-xs text-red-400">*</span>
                  )}
                  {activeTab === sub.id && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
                  )}
                </button>
              ))}
            </div>

            {/* Malus */}
            {activeTab === "malus" && (
              <div className="animate-in">
                <p className="mb-3 text-sm text-gray-400">
                  θ 从 90°（消光）到 0°，每 10° 记录左旋和右旋光强。
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

            {/* HalfWave */}
            {activeTab === "halfwave" && (
              <div className="animate-in">
                <div className="mb-4 rounded-lg border border-gray-100 bg-white p-4">
                  <h4 className="mb-3 text-sm font-medium">初始读数</h4>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    {[
                      { key: "c_deg", label: "C 初始 (度)" },
                      { key: "c_min", label: "C 初始 (分)" },
                      { key: "p2_deg", label: "P2 初始 (度)" },
                      { key: "p2_min", label: "P2 初始 (分)" },
                    ].map((f) => (
                      <label key={f.key} className="flex flex-col gap-1">
                        <span className="text-xs text-gray-400">
                          {f.label}
                        </span>
                        <input
                          type="number"
                          value={hwInit[f.key as keyof typeof hwInit]}
                          onChange={(e) =>
                            setHwInit((prev) => ({
                              ...prev,
                              [f.key]: e.target.value,
                            }))
                          }
                          className="h-8 rounded-md border border-border px-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/20"
                        />
                      </label>
                    ))}
                  </div>
                </div>
                <p className="mb-3 text-sm text-gray-400">
                  每次 C 转 10°，记录 C 和 P2 的刻度盘读数（度+分）。
                </p>
                <DataInputTable
                  headers={[
                    { label: "序号", readOnly: true },
                    { label: "C 读数 (度)" },
                    { label: "C 读数 (分)" },
                    { label: "P2 读数 (度)" },
                    { label: "P2 读数 (分)" },
                  ]}
                  data={hwData}
                  onChange={setHwData}
                />
              </div>
            )}

            {/* QuarterWave */}
            {activeTab === "quarterwave" && (
              <div className="animate-in">
                <p className="mb-3 text-sm text-gray-400">
                  P2 每转 10° 记录光强，共 36 个数据点 (φ = 0° ~ 350°)。
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

            {/* Circular */}
            {activeTab === "circular" && (
              <div className="animate-in">
                <p className="mb-3 text-sm text-gray-400">
                  圆偏振光通过检偏器，P2 每转 10° 记录光强，共 36 点。
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

            {/* Error */}
            {error && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Actions */}
            <div className="mt-8 flex justify-end gap-3">
              <button
                onClick={() => setStep("confirm")}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-6 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                确认数据
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === "confirm" && (
          <div className="animate-in mx-auto max-w-2xl">
            <div className="mb-8 text-center">
              <h2 className="mb-2 text-xl font-semibold">请确认原始数据</h2>
              <p className="text-sm text-gray-400">
                确认无误后点击"生成实验结果"
              </p>
            </div>

            {/* Data summary */}
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-100 bg-white p-7">
                <h3 className="mb-3 text-sm font-semibold">马吕斯定律数据</h3>
                <div className="text-xs text-gray-400">
                  {malusData.filter((r) => r[1] || r[2]).length} / 10 组数据已填写
                </div>
              </div>
              <div className="rounded-2xl border border-gray-100 bg-white p-7">
                <h3 className="mb-3 text-sm font-semibold">半波片数据</h3>
                <div className="text-xs text-gray-400">
                  {hwData.filter((r) => r[1] && r[3]).length} / 6 组数据已填写
                </div>
              </div>
              <div className="rounded-2xl border border-gray-100 bg-white p-7">
                <h3 className="mb-3 text-sm font-semibold">1/4 波片数据</h3>
                <div className="text-xs text-gray-400">
                  {qwData.filter((r) => r[1]).length} / 36 组数据已填写
                </div>
              </div>
              <div className="rounded-2xl border border-gray-100 bg-white p-7">
                <h3 className="mb-3 text-sm font-semibold">圆偏振光数据</h3>
                <div className="text-xs text-gray-400">
                  {circData.filter((r) => r[1]).length} / 36 组数据已填写
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-8 flex justify-center gap-3">
              <button
                onClick={() => setStep("input")}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-100 bg-white px-5 text-sm font-medium transition-colors hover:bg-gray-50"
              >
                返回修改
              </button>
              <button
                onClick={handleProcess}
                disabled={loading}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-6 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在计算...
                  </>
                ) : (
                  <>
                    生成实验结果
                    <ChevronRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Results */}
        {step === "results" && result?.status === "success" && (
          <div className="animate-in">
            {/* Success banner */}
            <div className="mb-8 flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 p-4">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <span className="text-sm font-medium text-green-800">
                数据处理完成
              </span>
            </div>

            {/* Results per sub-experiment */}
            <div className="space-y-8">
              {experiment.subExperiments.map((sub) => {
                const subResult = result.results[sub.id];
                if (!subResult) return null;
                const plotKey = sub.id;
                const plotData = result.plots[plotKey];

                return (
                  <div
                    key={sub.id}
                    className="rounded-2xl border border-gray-100 bg-white"
                  >
                    {/* Header */}
                    <div className="border-b border-border px-6 py-4">
                      <h3 className="text-base font-semibold">{sub.name}</h3>
                      <p className="text-sm text-gray-400">
                        {sub.description}
                      </p>
                    </div>

                    {/* Result fields */}
                    <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-5">
                      {sub.resultFields.map((field) => (
                        <div
                          key={field.key}
                          className="bg-white p-4"
                        >
                          <p className="text-xs text-gray-400 mb-1">
                            {field.label}
                          </p>
                          <p className="text-lg font-semibold tabular-nums">
                            {typeof subResult[field.key] === "number"
                              ? formatNumber(subResult[field.key])
                              : subResult[field.key] ?? "—"}
                            {field.unit && (
                              <span className="ml-1 text-xs font-normal text-gray-400">
                                {field.unit}
                              </span>
                            )}
                          </p>
                        </div>
                      ))}
                    </div>

                    {/* Plot */}
                    {plotData && (
                      <div className="border-t border-border p-6">
                        <div className="mb-4 flex items-center justify-between">
                          <h4 className="text-sm font-medium">实验图像</h4>
                          <button
                            onClick={() => downloadPlot(plotKey)}
                            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-gray-400 transition-colors hover:bg-gray-50"
                          >
                            <Download className="h-3 w-3" />
                            下载 PNG
                          </button>
                        </div>
                        <div className="flex justify-center rounded-lg bg-muted/50 p-4">
                          <img
                            src={`data:image/png;base64,${plotData}`}
                            alt={`${sub.name} 实验图像`}
                            className="max-h-[500px] w-auto object-contain"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Actions */}
            <div className="mt-8 flex justify-center gap-3">
              <button
                onClick={handleReset}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-100 bg-white px-5 text-sm font-medium transition-colors hover:bg-gray-50"
              >
                <RefreshCw className="h-4 w-4" />
                重新修改数据
              </button>
              <button
                onClick={downloadAllPlots}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-6 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                <Download className="h-4 w-4" />
                下载全部图像
              </button>
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
