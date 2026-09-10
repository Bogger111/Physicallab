"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
  type GenericExperimentConfig,
  type GenericExperimentData,
  type GenericProcessResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Draft = Record<string, { rows: Record<string, string>[]; params: Record<string, string> }>;

function makeDraft(config: GenericExperimentConfig): Draft {
  return Object.fromEntries(
    config.methods.map((method) => [
      method.id,
      {
        params: Object.fromEntries((method.params ?? []).map((parameter) => [
          parameter.key,
          String(parameter.default),
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
  const [config, setConfig] = useState<GenericExperimentConfig | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [active, setActive] = useState("");
  const [result, setResult] = useState<GenericProcessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
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

  const payload = useCallback((): GenericExperimentData => {
    if (!config) return {};
    return Object.fromEntries(config.methods.map((method) => {
      const source = draft[method.id];
      return [method.id, {
        params: Object.fromEntries((method.params ?? []).map((parameter) => [
          parameter.key,
          numeric(source?.params[parameter.key] ?? "") ?? parameter.default,
        ])),
        rows: (source?.rows ?? []).map((row) =>
          Object.fromEntries(method.columns.map((column) => [column.key, numeric(row[column.key] ?? "")]))
        ),
      }];
    }));
  }, [config, draft]);

  const current = useMemo(() => config?.methods.find((method) => method.id === active), [config, active]);

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

      <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
        {config.methods.map((method, index) => (
          <button key={method.id} onClick={() => setActive(method.id)} className={cn("shrink-0 rounded-xl border px-4 py-2.5 text-left transition-colors", active === method.id ? "border-indigo-600 bg-indigo-600 text-white" : "border-stone-200 bg-white text-stone-600 hover:border-stone-300")}>
            <span className="block text-xs font-bold">{index + 1}. {method.name}</span>
            <span className={cn("mt-0.5 block text-[10px]", active === method.id ? "text-indigo-100" : "text-stone-400")}>{method.required ? "必做" : "选做"}</span>
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
              {current.params.map((parameter) => <label key={parameter.key} className="text-xs font-semibold text-stone-500">{parameter.label} {parameter.unit && `(${parameter.unit})`}<input type="number" step="any" value={draft[current.id]?.params[parameter.key] ?? ""} onChange={(event) => updateParam(current.id, parameter.key, event.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-stone-200 px-3 text-right font-mono text-sm outline-none focus:border-indigo-400" /></label>)}
            </div>
          )}
          <div className="overflow-x-auto rounded-xl border border-stone-200">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <thead><tr>{current.columns.map((column) => <th key={column.key} className="whitespace-nowrap border-b border-stone-200 bg-stone-50 px-3 py-3 text-xs font-bold text-stone-500">{column.label}{column.unit && <span className="ml-1 font-normal text-stone-400">({column.unit})</span>}</th>)}</tr></thead>
              <tbody>{draft[current.id]?.rows.map((row, rowIndex) => <tr key={rowIndex} className="hover:bg-indigo-50/30">{current.columns.map((column) => <td key={column.key} className="border-b border-stone-100 p-0"><input type="number" step="any" value={row[column.key] ?? ""} onChange={(event) => updateCell(current.id, rowIndex, column.key, event.target.value)} onWheel={(event) => event.currentTarget.blur()} className="h-9 w-full min-w-24 border-0 bg-transparent px-3 text-right font-mono text-[13px] outline-none focus:bg-indigo-50" /></td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
      </section>

      <div className="mt-6 flex flex-col items-start justify-between gap-3 rounded-2xl border border-stone-200 bg-white p-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3"><FlaskConical className="h-5 w-5 text-indigo-600" /><div><p className="text-sm font-bold text-stone-900">统一处理全部已填写子实验</p><p className="text-xs text-stone-400">空白行会被忽略；必做数据不足时给出逐项提示</p></div></div>
        <div className="flex gap-2"><button onClick={() => { setDraft(makeDraft(config)); setResult(null); setError(null); }} className="inline-flex h-10 items-center gap-2 rounded-xl border border-stone-300 px-4 text-sm font-semibold text-stone-600"><RotateCcw className="h-4 w-4" />清空</button><button onClick={process} disabled={!!busy} className="inline-flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-5 text-sm font-semibold text-white disabled:opacity-50">{busy === "process" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}生成结果</button></div>
      </div>

      {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}

      {result?.status === "success" && (
        <div className="mt-8 space-y-6">
          <div className="flex flex-col justify-between gap-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5 sm:flex-row sm:items-center"><div className="flex items-center gap-3"><CheckCircle2 className="h-6 w-6 text-emerald-600" /><div><p className="font-bold text-stone-900">计算完成</p><p className="text-xs text-stone-500">{Object.keys(result.results).length} 个子实验已生成结果</p></div></div><div className="flex gap-2"><button onClick={() => act("docx", () => downloadGenericReport(id, "docx", payload()))} disabled={!!busy} className="inline-flex h-10 items-center gap-2 rounded-xl bg-stone-900 px-4 text-sm font-semibold text-white"><FileText className="h-4 w-4" />完整报告 Word</button><button onClick={() => act("pdf", () => downloadGenericReport(id, "pdf", payload()))} disabled={!!busy} className="inline-flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white"><Download className="h-4 w-4" />完整报告 PDF</button></div></div>
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
