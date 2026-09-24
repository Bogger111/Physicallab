"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Download,
  FileDown,
  FileText,
  FlaskConical,
  Loader2,
  Play,
  RotateCcw,
  Table2,
} from "lucide-react";
import {
  downloadGenericReport,
  downloadRecordSheet,
  fetchGenericConfig,
  previewRecordSheet,
  processGenericExperiment,
  trackEvent,
  type GenericExperimentConfig,
  type GenericExperimentData,
  type GenericProcessResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { getInputRange, isOutsideRange, rangeLabel } from "@/lib/input-ranges";
import OcrTableImporter from "./OcrTableImporter";
import DataContributionPanel from "./DataContributionPanel";
import { useDataCollection } from "@/hooks/useDataCollection";
import {
  completionState,
  nextGridCell,
  type CompletionMethod,
} from "./generic-workspace-logic";

type Draft = Record<string, { rows: Record<string, string>[]; params: Record<string, string> }>;

function rangeFor(id: string, methodId: string, field: { expected_range?: [number, number] }) {
  return field.expected_range
    ? { min: field.expected_range[0], max: field.expected_range[1] }
    : getInputRange(id, methodId, (field as { key?: string }).key ?? "");
}

function makeDraft(config: GenericExperimentConfig): Draft {
  return Object.fromEntries(
    config.methods.map((method) => [
      method.id,
      {
        params: Object.fromEntries((method.params ?? []).map((parameter) => [
          parameter.key,
          parameter.default === undefined || parameter.default === null
            ? ""                      // 实测参数（室温、预平衡 Rn）不预填，必须学生填
            : String(parameter.default),
        ])),
        rows: Array.from({ length: method.rowCount }, (_, rowIndex) =>
          Object.fromEntries(
            method.columns.map((column) => {
              const values = method.prefill?.[column.key] ?? [];
              return [column.key, rowIndex < values.length ? String(values[rowIndex]) : ""];
            })
          )
        ),
      },
    ])
  );
}

function numeric(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatValue(value: number | undefined): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 1e5 || (value !== 0 && Math.abs(value) < 1e-4)) {
    return value.toExponential(5);
  }
  return value.toFixed(6).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
}

export default function GenericExperimentWorkspace({ id }: { id: string }) {
  const collection = useDataCollection(id);
  const [config, setConfig] = useState<GenericExperimentConfig | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [active, setActive] = useState("");
  const [result, setResult] = useState<GenericProcessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRefs = useRef<(HTMLInputElement | null)[][]>([]);

  useEffect(() => {
    let alive = true;
    void trackEvent("workspace_start", id);
    fetchGenericConfig(id)
      .then((loaded) => {
        if (!alive) return;
        setConfig(loaded);
        setDraft(makeDraft(loaded));
        setActive(loaded.methods[0]?.id ?? "");
      })
      .catch((reason) => alive && setError(reason instanceof Error ? reason.message : "配置加载失败"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [id]);

  const payload = useCallback((methodIds?: string[]): GenericExperimentData => {
    if (!config) return {};
    const included = methodIds ? new Set(methodIds) : null;
    return Object.fromEntries(config.methods
      .filter((method) => !included || included.has(method.id))
      .map((method) => {
      const source = draft[method.id];
      const parameters: Record<string, number> = {};
      for (const parameter of method.params ?? []) {
        const value = numeric(source?.params[parameter.key] ?? "") ?? parameter.default;
        // 实测参数（室温 t、预平衡 Rn）没有 default，学生不填就不发送，由后端点名，绝不替学生编一个值
        if (value !== undefined && value !== null) parameters[parameter.key] = value;
      }
      return [method.id, {
        params: parameters,
        rows: (source?.rows ?? []).map((row) =>
          Object.fromEntries(method.columns.map((column) => [column.key, numeric(row[column.key] ?? "")]))
        ),
      }];
    }));
  }, [config, draft]);

  const current = useMemo(() => config?.methods.find((method) => method.id === active), [config, active]);
  const completionMethods = useMemo<CompletionMethod[]>(
    () => (config?.methods ?? []).map((method) => ({
      id: method.id,
      name: method.name,
      required: method.required,
      paramKeys: (method.params ?? []).map((parameter) => parameter.key),
      columnKeys: method.columns.map((column) => column.key),
    })),
    [config]
  );
  const completion = useMemo(
    () => completionState(completionMethods, draft),
    [completionMethods, draft]
  );
  const basicReady = completion.requiredAllComplete;

  const handleGridKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
    rowIndex: number,
    columnIndex: number
  ) => {
    if (!current || !event.key.startsWith("Arrow")) return;
    event.preventDefault();
    const destination = nextGridCell(
      event.key,
      rowIndex,
      columnIndex,
      draft[current.id]?.rows.length ?? 0,
      current.columns.length
    );
    if (destination) inputRefs.current[destination[0]]?.[destination[1]]?.focus();
  };

  const updateCell = (methodId: string, rowIndex: number, key: string, value: string) => {
    setDraft((previous) => ({
      ...previous,
      [methodId]: {
        ...previous[methodId],
        rows: previous[methodId].rows.map((row, index) => index === rowIndex ? { ...row, [key]: value } : row),
      },
    }));
    setResult(null);
  };

  const updateParam = (methodId: string, key: string, value: string) => {
    setDraft((previous) => ({
      ...previous,
      [methodId]: { ...previous[methodId], params: { ...previous[methodId].params, [key]: value } },
    }));
    setResult(null);
  };

  const applyCurrentOCR = (values: string[], overwriteExisting: boolean) => {
    if (!current) return;
    setDraft((previous) => {
      let valueIndex = 0;
      const rows = previous[current.id].rows.map((row) => {
        const next = { ...row };
        current.columns.forEach((column) => {
          const value = values[valueIndex++]?.trim();
          if (!value) return;
          if (!overwriteExisting && (next[column.key] ?? "").trim()) return;
          next[column.key] = value;
        });
        return next;
      });
      return { ...previous, [current.id]: { ...previous[current.id], rows } };
    });
    setResult(null);
  };

  const act = async (key: string, action: () => Promise<void>) => {
    if (busy) return;
    setBusy(key); setError(null);
    try { await action(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(null); }
  };

  const process = () => act("process", async () => {
    const response = await processGenericExperiment(id, payload());
    setResult(response);
    if (response.status !== "success") setError(response.errors.join("；") || "没有足够的有效数据");
  });

  const reportPayload = (): GenericExperimentData => payload(completion.completedMethodIds);
  const downloadFinalReport = async (format: "docx" | "pdf") => {
    const data = reportPayload();
    await downloadGenericReport(id, format, data);
    await collection.commit(data);
  };

  if (loading) return <div className="container-x flex min-h-[55vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-indigo-600" /></div>;
  if (!config || !current) return <div className="container-x py-16 text-center text-red-600">{error ?? "实验配置不存在"}</div>;

  return (
    <div className="container-x py-8 sm:py-12">
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <Link href={`/experiments/${id}`} className="mb-3 inline-flex items-center gap-1.5 text-sm font-semibold text-stone-400 hover:text-stone-700"><ArrowLeft className="h-4 w-4" />实验说明</Link>
          <h1 className="text-2xl font-extrabold tracking-tight text-stone-900 sm:text-3xl">{config.name}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-stone-500">{config.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => act("preview", () => previewRecordSheet(id))} disabled={!!busy} className="inline-flex h-10 items-center gap-2 rounded-xl border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-700 disabled:opacity-50"><FileText className="h-4 w-4" />预览记录表</button>
          <button onClick={() => act("record", () => downloadRecordSheet("docx", id))} disabled={!!busy} className="inline-flex h-10 items-center gap-2 rounded-xl bg-stone-900 px-4 text-sm font-semibold text-white disabled:opacity-50"><FileDown className="h-4 w-4" />记录表 Word</button>
        </div>
      </div>

      <DataContributionPanel collection={collection} />

      <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
        {config.methods.map((method, index) => (
          <button key={method.id} onClick={() => setActive(method.id)} className={cn("shrink-0 rounded-xl border px-4 py-2.5 text-left transition-colors", active === method.id ? "border-indigo-600 bg-indigo-600 text-white" : "border-stone-200 bg-white text-stone-600 hover:border-stone-300")}>
            <span className="block text-xs font-bold">{index + 1}. {method.name}</span>
            <span className={cn("mt-0.5 block text-[10px]", active === method.id ? "text-indigo-100" : "text-stone-400")}>
              {method.required ? "必做" : "选做"}{completion.completedMethodIds.includes(method.id) ? " · 已填" : ""}
            </span>
          </button>
        ))}
      </div>

      <section className="card overflow-hidden shadow-soft">
        <div className="border-b border-stone-100 bg-stone-50/70 px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white"><Table2 className="h-4.5 w-4.5" /></span><div><h2 className="font-bold text-stone-900">{current.name}</h2><p className="text-xs text-stone-400">{current.description}</p></div></div>
        </div>
        <div className="p-5 sm:p-6">
          {!!current.params?.length && (
            <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {current.params.map((parameter) => (
                <label key={parameter.key} className="text-xs font-semibold text-stone-500">
                  {parameter.label} {parameter.unit && `(${parameter.unit})`}
                  <span className="mt-0.5 block text-[10px] font-medium text-amber-600">
                    {rangeLabel(rangeFor(id, current.id, parameter), parameter.unit)}
                  </span>
                  <input
                    type="number"
                    step="any"
                    value={draft[current.id]?.params[parameter.key] ?? ""}
                    onChange={(event) => updateParam(current.id, parameter.key, event.target.value)}
                    onWheel={(event) => event.currentTarget.blur()}
                    aria-invalid={isOutsideRange(draft[current.id]?.params[parameter.key] ?? "", rangeFor(id, current.id, parameter)) || undefined}
                    className={cn("mt-1.5 h-10 w-full rounded-lg border px-3 text-right font-mono text-sm outline-none", isOutsideRange(draft[current.id]?.params[parameter.key] ?? "", rangeFor(id, current.id, parameter)) ? "border-amber-300 bg-amber-50 text-amber-900" : "border-stone-200 focus:border-indigo-400")}
                  />
                </label>
              ))}
            </div>
          )}
          {!!current.params?.some((parameter) => parameter.hint) && (
            <ul className="mb-6 space-y-1 rounded-lg bg-stone-50 px-3 py-2">
              {current.params.filter((parameter) => parameter.hint).map((parameter) => (
                <li key={parameter.key} className="text-[10px] leading-snug text-stone-400">
                  {parameter.label}{parameter.unit ? `（${parameter.unit}）` : ""}：{parameter.hint}
                </li>
              ))}
            </ul>
          )}
          <OcrTableImporter
            experimentId={id}
            tableId={current.id}
            expectedCellCount={current.rowCount * current.columns.length}
            onApply={applyCurrentOCR}
          />
          <div className="overflow-x-auto rounded-xl border border-stone-200">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <thead><tr>{current.columns.map((column) => <th key={column.key} className="whitespace-nowrap border-b border-stone-200 bg-stone-50 px-3 py-3 text-xs font-bold text-stone-500">{column.label}{column.unit && <span className="ml-1 font-normal text-stone-400">({column.unit})</span>}<span className="mt-0.5 block text-[10px] font-normal text-amber-600">{rangeLabel(rangeFor(id, current.id, column), column.unit)}</span></th>)}</tr></thead>
              <tbody>
                {draft[current.id]?.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="hover:bg-indigo-50/30">
                    {current.columns.map((column, columnIndex) => (
                      <td key={column.key} className="border-b border-stone-100 p-0">
                        <input
                          ref={(element) => {
                            inputRefs.current[rowIndex] ??= [];
                            inputRefs.current[rowIndex][columnIndex] = element;
                          }}
                          type="number"
                          step="any"
                          value={row[column.key] ?? ""}
                          onChange={(event) => updateCell(current.id, rowIndex, column.key, event.target.value)}
                          onKeyDown={(event) => handleGridKeyDown(event, rowIndex, columnIndex)}
                          onWheel={(event) => event.currentTarget.blur()}
                          aria-invalid={isOutsideRange(row[column.key] ?? "", rangeFor(id, current.id, column)) || undefined}
                          title={isOutsideRange(row[column.key] ?? "", rangeFor(id, current.id, column)) ? `${rangeLabel(rangeFor(id, current.id, column), column.unit)}；当前值可能需要检查` : rangeLabel(rangeFor(id, current.id, column), column.unit)}
                          className={cn("h-9 w-full min-w-24 border-0 px-3 text-right font-mono text-[13px] outline-none", isOutsideRange(row[column.key] ?? "", rangeFor(id, current.id, column)) ? "bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-300" : "bg-transparent focus:bg-indigo-50")}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <div className={cn(
        "mt-6 flex flex-col items-start justify-between gap-4 rounded-2xl border p-5 sm:flex-row sm:items-center",
        completion.requiredAllComplete ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50"
      )}>
        <div className="flex items-start gap-3">
          {completion.requiredAllComplete
            ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            : <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />}
          <div>
            <p className="text-sm font-bold text-stone-900">
              必做实验完成度：{completion.completedRequiredCount}/{completion.requiredCount}
            </p>
            <p className="mt-1 text-xs text-stone-500">
              {completion.requiredAllComplete
                ? "必做数据已填完整，可直接生成完整报告；选做实验填完整后自动并入。"
                : `请先填完：${completion.missingRequiredNames.join("、")}`}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { setDraft(makeDraft(config)); setResult(null); setError(null); }} className="inline-flex h-10 items-center gap-2 rounded-xl border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-600"><RotateCcw className="h-4 w-4" />清空</button>
          <button
            onClick={process}
            disabled={!!busy}
            title="预览当前已填写子实验的计算结果"
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-indigo-200 bg-white px-4 text-sm font-semibold text-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy === "process" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            预览结果
          </button>
          <button
            onClick={() => act("docx", () => downloadFinalReport("docx"))}
            disabled={!!busy || !basicReady}
            title={basicReady ? "直接生成完整报告 Word" : "请先填写完全部必做实验"}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-stone-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
          ><FileText className="h-4 w-4" />报告 Word</button>
          <button
            onClick={() => act("pdf", () => downloadFinalReport("pdf"))}
            disabled={!!busy || !basicReady}
            title={basicReady ? "直接生成完整报告 PDF" : "请先填写完全部必做实验"}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
          ><Download className="h-4 w-4" />报告 PDF</button>
        </div>
      </div>

      {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      {result?.warnings?.length ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-bold">数据合理性提醒</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          <p className="mt-2 text-xs">范围仅用于提醒，不会自动修改或阻止你的真实测量值。</p>
        </div>
      ) : null}

      {result && Object.keys(result.results).length > 0 && (
        <div className="mt-8 space-y-6">
          <div className={cn("flex flex-col justify-between gap-4 rounded-2xl border p-5 sm:flex-row sm:items-center", result.status === "success" ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/60")}>
            <div className="flex items-center gap-3">
              {result.status === "success" ? <CheckCircle2 className="h-6 w-6 text-emerald-600" /> : <AlertCircle className="h-6 w-6 text-amber-600" />}
              <div>
                <p className="font-bold text-stone-900">{result.status === "success" ? "计算完成" : "部分计算完成"}</p>
                <p className="text-xs text-stone-500">{Object.keys(result.results).length} 个子实验已生成结果{result.status !== "success" ? "；请补齐提示的数据后再生成完整报告" : ""}</p>
              </div>
            </div>
            {result.status === "success" && <div className="flex flex-wrap gap-2">
              <button
                onClick={() => act("docx", () => downloadFinalReport("docx"))}
                disabled={!!busy || !basicReady}
                title={basicReady ? "下载完整报告 Word" : "填写完全部必做实验后才能生成报告"}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-stone-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              ><FileText className="h-4 w-4" />完整报告 Word</button>
              <button
                onClick={() => act("pdf", () => downloadFinalReport("pdf"))}
                disabled={!!busy || !basicReady}
                title={basicReady ? "下载完整报告 PDF" : "填写完全部必做实验后才能生成报告"}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              ><Download className="h-4 w-4" />完整报告 PDF</button>
            </div>}
          </div>
          {!basicReady && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              报告尚未解锁：请先填写完{completion.missingRequiredNames.join("、")}。
            </div>
          )}
          {result.errors.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">部分数据未纳入：{result.errors.join("；")}</div>}
          {config.methods.map((method) => {
            const values = result.results[method.id]; if (!values) return null;
            return <section key={method.id} className="card overflow-hidden shadow-soft"><div className="flex items-center gap-3 border-b border-stone-100 bg-stone-50/70 px-5 py-4"><BarChart3 className="h-5 w-5 text-indigo-600" /><h3 className="font-bold text-stone-900">{method.name}</h3></div><div className="grid gap-px bg-stone-100 sm:grid-cols-2 lg:grid-cols-4">{method.results.map((field) => <div key={field.key} className="bg-white p-4"><p className="text-xs text-stone-400">{field.label}</p><p className="mt-1 font-mono text-lg font-bold text-stone-900">{formatValue(values[field.key])}<span className="ml-1 text-xs font-medium text-stone-400">{field.unit}</span></p></div>)}</div>{result.plots[method.id] && <div className="border-t border-stone-100 p-5"><img src={`data:image/png;base64,${result.plots[method.id]}`} alt={`${method.name}结果图`} className="mx-auto max-h-[460px] max-w-full" /></div>}</section>;
          })}
        </div>
      )}
    </div>
  );
}
