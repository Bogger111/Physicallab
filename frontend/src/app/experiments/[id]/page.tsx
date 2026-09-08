"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Download,
  FileDown,
  Eye,
  Clock3,
  FlaskConical,
  ChevronRight,
  Layers,
  PenLine,
  Sheet,
  ChartSpline,
  Lock,
  Loader2,
} from "lucide-react";
import { getExperiment } from "@/lib/experiments";
import { downloadRecordSheet, previewRecordSheet } from "@/lib/api";
import { cn } from "@/lib/utils";

const CAT_CHIP: Record<string, string> = {
  光学: "bg-amber-100 text-amber-800 ring-amber-200",
  力学: "bg-sky-100 text-sky-800 ring-sky-200",
  热学: "bg-orange-100 text-orange-800 ring-orange-200",
  电磁学: "bg-fuchsia-100 text-fuchsia-800 ring-fuchsia-200",
  近代物理: "bg-teal-100 text-teal-800 ring-teal-200",
};

const FLOW = [
  { icon: FileDown, title: "下载记录表", desc: "打印空白数据表" },
  { icon: PenLine, title: "完成实验", desc: "实验室手写记录" },
  { icon: Sheet, title: "录入数据", desc: "回传原始读数" },
  { icon: ChartSpline, title: "生成结果", desc: "自动计算与出图" },
] as const;

export default function ExperimentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const experiment = getExperiment(id);
  const [sheetBusy, setSheetBusy] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);

  const grab = async (key: string, action: () => Promise<void>) => {
    if (sheetBusy) return;
    setSheetBusy(key);
    setSheetError(null);
    try {
      await action();
    } catch (e) {
      setSheetError(e instanceof Error ? e.message : "下载失败");
    } finally {
      setSheetBusy(null);
    }
  };

  if (!experiment) {
    return (
      <div className="container-x flex flex-col items-center py-28 text-center">
        <span className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-stone-100 text-stone-400">
          <FlaskConical className="h-7 w-7" />
        </span>
        <p className="text-lg font-bold text-stone-800">未找到该实验</p>
        <p className="mt-1.5 text-sm text-stone-400">实验可能已下线或链接有误</p>
        <Link
          href="/experiments"
          className="mt-7 inline-flex h-11 items-center gap-2 rounded-xl bg-indigo-600 px-6 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
        >
          <ArrowLeft className="h-4 w-4" />
          返回实验库
        </Link>
      </div>
    );
  }

  const required = experiment.subExperiments.filter((s) => s.required).length;
  const chip = CAT_CHIP[experiment.category] ?? "bg-indigo-100 text-indigo-800 ring-indigo-200";
  const statTiles = [
    { value: String(experiment.subExperiments.length), label: "子实验" },
    { value: String(required), label: "必做环节" },
    { value: String(experiment.measurements.length), label: "待记物理量" },
  ];

  return (
    <div className="container-x py-10 sm:py-14">
      {/* Breadcrumb */}
      <nav className="mb-8 flex items-center gap-1.5 text-sm" aria-label="面包屑">
        <Link
          href="/experiments"
          className="inline-flex items-center gap-1.5 font-medium text-stone-400 transition-colors hover:text-stone-800"
        >
          <ArrowLeft className="h-4 w-4" />
          实验库
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-stone-300" aria-hidden />
        <span className="font-semibold text-stone-700">{experiment.name}</span>
      </nav>

      {/* ======= Cover card ======= */}
      <section className="card relative overflow-hidden p-7 shadow-soft sm:p-10">
        <div className="pointer-events-none absolute inset-0 bg-dots opacity-50 [mask-image:linear-gradient(120deg,black,transparent_55%)]" />
        <div className="pointer-events-none absolute -right-28 -top-28 h-72 w-72 rounded-full bg-gradient-to-br from-indigo-200/60 via-violet-200/40 to-transparent blur-2xl" />

        <div className="relative grid items-center gap-8 lg:grid-cols-[1.35fr_1fr]">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset",
                  chip
                )}
              >
                {experiment.category}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-500">
                <Clock3 className="h-3.5 w-3.5" />
                {experiment.processingTime} 完成处理
              </span>
            </div>

            <h1 className="text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">
              {experiment.name}
            </h1>
            <p className="mt-3.5 max-w-xl text-[15px] leading-relaxed text-stone-500 sm:text-base">
              {experiment.description}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href={`/experiments/${experiment.id}/workspace`}
                className="group inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-7 text-[15px] font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-700 hover:shadow-xl"
              >
                开始数据处理
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <button
                onClick={() => grab("cover-pdf", () => downloadRecordSheet("pdf"))}
                disabled={sheetBusy !== null}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white/80 px-6 text-[15px] font-semibold text-stone-700 backdrop-blur transition-colors hover:border-stone-400 hover:bg-white disabled:opacity-50"
              >
                {sheetBusy === "cover-pdf" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4 text-indigo-600" />
                )}
                下载记录表
              </button>
              {sheetError && (
                <p className="mt-2 text-xs font-medium text-red-500" role="alert">
                  {sheetError}
                </p>
              )}
            </div>
          </div>

          {/* Right stats panel */}
          <div className="rounded-2xl border border-stone-200/70 bg-white/70 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.14em] text-stone-400">
                <Layers className="h-3.5 w-3.5" />
                任务概览
              </span>
              <span className="text-[11px] font-medium text-stone-300">本页数据自动生成</span>
            </div>
            <div className="mb-5 grid grid-cols-3 gap-2">
              {statTiles.map((s) => (
                <div key={s.label} className="rounded-xl bg-stone-50 py-3.5 text-center ring-1 ring-inset ring-stone-100">
                  <p className="text-xl font-extrabold tabular-nums text-indigo-700">{s.value}</p>
                  <p className="mt-0.5 text-[11px] font-medium text-stone-400">{s.label}</p>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {experiment.subExperiments.slice(0, 3).map((sub) => (
                <div key={sub.id} className="flex items-center gap-2.5 rounded-lg px-1.5 py-1">
                  <span
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold",
                      sub.required
                        ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white"
                        : "border border-stone-200 text-stone-400"
                    )}
                  >
                    {sub.required ? "必" : "选"}
                  </span>
                  <span className="truncate text-[13px] font-medium text-stone-600">{sub.name}</span>
                  <span className="ml-auto shrink-0 text-[11px] tabular-nums text-stone-300">
                    {sub.resultFields.length} 项结果
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ======= Body ======= */}
      <div className="mx-auto mt-12 max-w-3xl space-y-12">
        {/* Measurements */}
        <section>
          <SectionHead kicker="Measurements" title="需要记录的数据" hint={`共 ${experiment.measurements.length} 项`} />
          <div className="flex flex-wrap gap-2.5">
            {experiment.measurements.map((m, i) => (
              <span
                key={m}
                className="inline-flex items-center gap-2 rounded-xl border border-stone-200/80 bg-white px-4 py-2.5 text-sm text-stone-700 shadow-sm"
              >
                <span className="font-mono text-xs font-bold tabular-nums text-indigo-600">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {m}
              </span>
            ))}
          </div>
          <p className="mt-3.5 text-xs leading-relaxed text-stone-400">
            记录表已按这些物理量排版，实验时逐格填写即可，无需整理格式。
          </p>
        </section>

        {/* Record sheet download */}
        <section>
          <SectionHead kicker="Record Sheet" title="实验数据记录表" />
          <div className="relative overflow-hidden rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/90 via-white to-violet-50/80 p-6 sm:p-7">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white text-indigo-600 shadow-sm ring-1 ring-inset ring-indigo-100">
                  <FileDown className="h-6 w-6" />
                </span>
                <div>
                  <h3 className="text-[15px] font-bold text-stone-900">标准数据记录表 · PDF</h3>
                  <p className="mt-1 text-sm leading-relaxed text-stone-500">
                    A4 打印版，已含全部子实验表格。实验前打印，完成后即可回来录入。
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2.5">
                <button
                  onClick={() => grab("preview", previewRecordSheet)}
                  disabled={sheetBusy !== null}
                  className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-900 disabled:opacity-50"
                >
                  <Eye className="h-4 w-4" />
                  预览
                </button>
                <button
                  onClick={() => grab("sheet-docx", () => downloadRecordSheet("docx"))}
                  disabled={sheetBusy !== null}
                  className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-stone-900 px-4 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-stone-700 disabled:opacity-50"
                >
                  {sheetBusy === "sheet-docx" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileDown className="h-4 w-4" />
                  )}
                  下载 Word
                </button>
                <button
                  onClick={() => grab("sheet-pdf", () => downloadRecordSheet("pdf"))}
                  disabled={sheetBusy !== null}
                  className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white shadow-sm shadow-indigo-600/25 transition-colors hover:bg-indigo-700 disabled:opacity-50"
                >
                  {sheetBusy === "sheet-pdf" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  下载 PDF
                </button>
              </div>
              {sheetError && (
                <p className="mt-2 text-xs font-medium text-red-500" role="alert">
                  {sheetError}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Flow */}
        <section>
          <SectionHead kicker="Workflow" title="操作流程" hint="四步，一条龙" />
          <div className="card p-6 sm:p-8">
            <div className="relative grid grid-cols-2 gap-y-8 md:grid-cols-4">
              <span
                aria-hidden
                className="absolute left-[16%] right-[16%] top-5 hidden h-px bg-gradient-to-r from-indigo-200 via-stone-200 to-violet-200 md:block"
              />
              {FLOW.map((step, i) => (
                <div key={step.title} className="relative flex flex-col items-center text-center">
                  <span className="relative z-10 mb-3.5 flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30">
                    <step.icon className="h-[18px] w-[18px]" strokeWidth={2} />
                  </span>
                  <p className="text-sm font-bold text-stone-800">
                    <span className="mr-1.5 font-mono text-[11px] font-bold text-indigo-500">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {step.title}
                  </p>
                  <p className="mt-1 text-xs text-stone-400">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Sub-experiments */}
        <section>
          <SectionHead kicker="Modules" title="包含的子实验" hint={`${experiment.subExperiments.length} 个`} />
          <div className="card divide-y divide-stone-100 overflow-hidden">
            {experiment.subExperiments.map((sub) => (
              <div key={sub.id} className="flex items-start gap-4 p-5 transition-colors hover:bg-stone-50/80 sm:px-6">
                <span
                  className={cn(
                    "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold",
                    sub.required
                      ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-600/25"
                      : "border border-stone-200 bg-white text-stone-400"
                  )}
                >
                  {sub.required ? "必" : "选"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-bold text-stone-900">{sub.name}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-stone-500">{sub.description}</p>
                </div>
                <span className="mt-1 hidden shrink-0 rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium tabular-nums text-stone-500 sm:inline-flex">
                  输出 {sub.resultFields.length} 项结果
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* ======= Bottom CTA ======= */}
      <section className="mx-auto mt-14 max-w-3xl">
        <div className="relative overflow-hidden rounded-3xl bg-panel-dark p-8 text-center sm:p-12">
          <div className="pointer-events-none absolute inset-0 bg-dots-white opacity-50" />
          <div className="relative">
            <h2 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
              做完实验了？回来把数据交给我们
            </h2>
            <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-indigo-200/75">
              录入原始读数即可，计算、拟合、绘图与结果表将自动生成。
            </p>
            <Link
              href={`/experiments/${experiment.id}/workspace`}
              className="group mt-8 inline-flex h-12 items-center gap-2 rounded-xl bg-white px-8 text-[15px] font-bold text-indigo-950 shadow-xl shadow-black/20 transition-all hover:-translate-y-0.5 hover:shadow-2xl"
            >
              进入数据处理工作台
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <p className="mt-5 inline-flex items-center gap-1.5 text-xs text-white/40">
              <Lock className="h-3 w-3" />
              数据仅在你的设备与本地服务之间传输
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function SectionHead({
  kicker,
  title,
  hint,
}: {
  kicker: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-5 flex items-end justify-between">
      <div>
        <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.22em] text-indigo-500">
          {kicker}
        </p>
        <h2 className="flex items-center gap-2.5 text-xl font-extrabold tracking-tight text-stone-900 sm:text-2xl">
          {title}
          {hint && (
            <span className="rounded-full bg-stone-200/70 px-2.5 py-0.5 text-xs font-semibold tabular-nums text-stone-500">
              {hint}
            </span>
          )}
        </h2>
      </div>
    </div>
  );
}
