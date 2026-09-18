"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, Database, KeyRound, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { fetchDataCollectionStats, type DataCollectionStats } from "@/lib/api";

/**
 * Developer-only view of the contribution loop.
 *
 * Not linked from the public navigation and gated twice: the page renders only
 * when `NEXT_PUBLIC_PHYSICSLAB_DEV_MODE=true` is baked into this build, and the
 * backend answers `/api/data-collection/stats` only for a configured
 * `PHYSICSLAB_ADMIN_KEY` (header `X-Admin-Key`) or in local development mode.
 */
export default function DataCollectionDashboard() {
  const devMode = process.env.NEXT_PUBLIC_PHYSICSLAB_DEV_MODE === "true";
  const [stats, setStats] = useState<DataCollectionStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adminKey, setAdminKey] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    setAdminKey(window.localStorage.getItem("physlab:admin-key") ?? "");
  }, []);

  const load = useCallback(
    async (key?: string) => {
      setLoading(true);
      setError(null);
      try {
        setStats(await fetchDataCollectionStats(key || undefined));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "统计数据不可用");
        setStats(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (!devMode) return;
    void load();
  }, [devMode, load]);

  if (!devMode) {
    return (
      <main className="container-x py-16">
        <div className="mx-auto max-w-xl rounded-2xl border border-stone-200 bg-white p-6 text-center">
          <ShieldAlert className="mx-auto h-6 w-6 text-stone-400" />
          <h1 className="mt-3 text-lg font-bold text-stone-900">开发者面板未启用</h1>
          <p className="mt-2 text-sm text-stone-500">
            该页面仅在开发模式下可用。请在 <code className="font-mono text-xs">frontend/.env.local</code> 中设置{" "}
            <code className="font-mono text-xs">NEXT_PUBLIC_PHYSICSLAB_DEV_MODE=true</code> 后重新构建。
          </p>
        </div>
      </main>
    );
  }

  const experiments = stats ? Object.entries(stats.experiments).sort((a, b) => b[1] - a[1]) : [];

  return (
    <main className="container-x py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">Developer</p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-stone-900">
            <BarChart3 className="h-6 w-6 text-indigo-600" />
            Data Collection
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-stone-500">
            数据共建总览。统计只读取 session metadata 与数据集索引（samples.csv），不扫描任何图片。
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(adminKey)}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 text-xs font-semibold text-stone-700"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          刷新
        </button>
      </div>

      {error && (
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">{error}</p>
          <p className="mt-1 text-xs leading-5">
            该接口不公开：后端需配置 <code className="font-mono">PHYSICSLAB_ADMIN_KEY</code>（并在下方填入相同的密钥），
            或在本地开发环境设置 <code className="font-mono">PHYSICSLAB_DEV_MODE=true</code>。
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              type="password"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              placeholder="X-Admin-Key"
              className="h-9 w-64 rounded-lg border border-stone-300 px-3 font-mono text-xs"
            />
            <button
              type="button"
              onClick={() => {
                window.localStorage.setItem("physlab:admin-key", adminKey);
                void load(adminKey);
              }}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-stone-900 px-3 text-xs font-semibold text-white"
            >
              <KeyRound className="h-3.5 w-3.5" />使用该密钥
            </button>
          </div>
        </div>
      )}

      {stats && (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["总实验数 Sessions", stats.total_sessions],
              ["AI 贡献 Contributions", stats.collection_sessions ?? stats.confirmed_sessions],
              ["OCR Samples", stats.samples_created],
              ["待确认数值", stats.sessions_awaiting_values ?? Math.max(0, stats.total_sessions - stats.confirmed_sessions)],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-2xl border border-stone-200 bg-white p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">{label}</p>
                <p className="mt-2 text-3xl font-extrabold tabular-nums text-stone-900">{value}</p>
              </div>
            ))}
          </div>

          <section className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-sm font-bold text-stone-900">
                <Database className="h-4 w-4 text-indigo-600" />Experiments
              </h2>
              <p className="text-xs text-stone-500">
                普通实验 {stats.plain_sessions ?? 0} 个（不采集） · AI 共建{" "}
                {stats.collection_sessions ?? 0} 个（其中已确认 {stats.collection_confirmed_sessions ?? 0} 个）
              </p>
            </div>
            {experiments.length === 0 ? (
              <p className="mt-3 text-sm text-stone-500">还没有实验数据。</p>
            ) : (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-stone-400">
                    <th className="py-2 font-semibold">实验</th>
                    <th className="py-2 text-right font-semibold">OCR 样本</th>
                    <th className="py-2 text-right font-semibold">Sessions</th>
                    <th className="py-2 text-right font-semibold">Confirmed</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.map(([experiment, samples]) => (
                    <tr key={experiment} className="border-t border-stone-100">
                      <td className="py-2 font-medium text-stone-800">{experiment}</td>
                      <td className="py-2 text-right tabular-nums text-stone-700">{samples}</td>
                      <td className="py-2 text-right tabular-nums text-stone-500">
                        {stats.sessions_by_experiment?.[experiment] ?? 0}
                      </td>
                      <td className="py-2 text-right tabular-nums text-stone-500">
                        {stats.confirmed_by_experiment?.[experiment] ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {stats.dataset && (
              <p className="mt-4 border-t border-stone-100 pt-3 text-xs text-stone-500">
                数据集导出目录 <code className="font-mono">{stats.dataset.export}</code>：
                {stats.dataset.labeled_samples} 条已标注样本、{stats.dataset.image_files} 个裁剪图、
                来自 {stats.dataset.sessions_in_dataset} 个会话。
              </p>
            )}
          </section>

          <p className="mt-4 text-xs text-stone-400">
            {stats.generated_at ? `统计时间 ${stats.generated_at}` : null}
          </p>
        </>
      )}
    </main>
  );
}
