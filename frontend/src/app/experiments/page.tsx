"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowRight, Clock3, FlaskConical, Layers, Sparkles } from "lucide-react";
import { experiments, categories } from "@/lib/experiments";
import { withCollectionMode } from "@/lib/collection-mode";
import { useCollectionMode } from "@/hooks/useCollectionMode";
import { cn } from "@/lib/utils";

const CAT_STYLE: Record<string, string> = {
  光学: "bg-amber-100 text-amber-800 ring-amber-200",
  力学: "bg-sky-100 text-sky-800 ring-sky-200",
  波动: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  热学: "bg-orange-100 text-orange-800 ring-orange-200",
  电磁学: "bg-fuchsia-100 text-fuchsia-800 ring-fuchsia-200",
  近代物理: "bg-teal-100 text-teal-800 ring-teal-200",
};

function ExperimentsPage() {
  const collectionMode = useCollectionMode();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("全部");

  const filtered = useMemo(
    () =>
            experiments.filter((exp) => !exp.hidden).filter((exp) => {
        const matchSearch =
          !search ||
          exp.name.toLowerCase().includes(search.toLowerCase()) ||
          exp.description.toLowerCase().includes(search.toLowerCase());
        const matchCategory = category === "全部" || exp.category === category;
        return matchSearch && matchCategory;
      }),
            [search, category]
  );

  return (
    <div className="container-x py-12 sm:py-16">
      {/* Page header */}
      <div className="mb-10 max-w-2xl">
        <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50/70 px-3 py-1 text-xs font-bold tracking-[0.14em] text-indigo-600">
          <Layers className="h-3.5 w-3.5" />
          EXPERIMENT LIBRARY
        </p>
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">
            实验库
          </h1>
          <span className="text-sm font-semibold text-stone-400">
            共 {experiments.filter((exp) => !exp.hidden).length} 个实验
          </span>
        </div>
        <p className="mt-2.5 text-[15px] leading-relaxed text-stone-500">
          选择实验下载标准记录表，实验后回来录入数据，自动完成计算、拟合与出图。
        </p>
      </div>

      {collectionMode && (
        <div className="mb-6 flex flex-wrap items-start gap-3 rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
          <p className="text-xs leading-6 text-stone-600">
            <span className="font-bold text-indigo-800">AI 实验共建模式已开启。</span>
            实验流程与普通模式完全一致；实验完成后，你可以自愿上传脱敏后的原始记录表，帮助 PhysLab
            学习真实实验记录。随时可以撤回贡献，也可以在实验详情页切回普通模式。
          </p>
        </div>
      )}

      {/* Toolbar */}
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-sm">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <input
            type="text"
            placeholder="搜索实验名称或内容…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="搜索实验"
            className="h-11 w-full rounded-xl border border-stone-200 bg-white pl-10 pr-4 text-sm text-stone-900 shadow-sm outline-none transition-all placeholder:text-stone-400 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
          />
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="按分类筛选">
          {categories.map((cat) => {
            const active = category === cat;
            return (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                aria-pressed={active}
                className={cn(
                  "h-9 rounded-full px-4 text-[13px] font-medium transition-all",
                  active
                    ? "bg-stone-900 text-white shadow-md shadow-stone-900/20"
                    : "border border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-stone-800"
                )}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Cards */}
      {filtered.length > 0 ? (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((exp) => {
            const required = exp.subExperiments.filter((s) => s.required).length;
            const catChip = CAT_STYLE[exp.category] ?? "bg-indigo-100 text-indigo-800 ring-indigo-200";
            return (
              <Link
                key={exp.id}
                href={withCollectionMode(`/experiments/${exp.id}`, collectionMode)}
                className="group relative flex flex-col overflow-hidden rounded-2xl border border-stone-200/80 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-indigo-200 hover:shadow-lift"
              >
                {/* top accent on hover */}
                <span
                  aria-hidden
                  className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-indigo-500 to-violet-500 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
                />

                <div className="mb-5 flex items-center justify-between">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
                      catChip
                    )}
                  >
                    {exp.category}
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-400">
                    <Clock3 className="h-3.5 w-3.5" />
                    {exp.processingTime}
                  </span>
                </div>

                <h3 className="mb-2 text-lg font-bold tracking-tight text-stone-900 transition-colors group-hover:text-indigo-700">
                  {exp.name}
                </h3>
                <p className="mb-6 line-clamp-2 text-sm leading-relaxed text-stone-500">
                  {exp.description}
                </p>

                <div className="mt-auto flex items-end justify-between border-t border-dashed border-stone-200 pt-4">
                  <span className="flex items-center gap-1.5 text-xs text-stone-400">
                    <FlaskConical className="h-3.5 w-3.5" />
                    {exp.subExperiments.length} 个子实验
                    {required > 0 && <span className="text-stone-300">· 必做 {required}</span>}
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-600">
                    开始实验
                    <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className="card flex flex-col items-center gap-4 px-6 py-24 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-stone-100 text-stone-400">
            <Search className="h-6 w-6" />
          </span>
          <p className="text-base font-semibold text-stone-700">未找到匹配的实验</p>
          <p className="-mt-2 text-sm text-stone-400">换个关键词或分类试试</p>
          <button
            onClick={() => {
              setSearch("");
              setCategory("全部");
            }}
            className="mt-1 inline-flex h-10 items-center rounded-lg bg-indigo-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
          >
            清除筛选
          </button>
        </div>
      )}
    </div>
  );
}

export default function ExperimentsRoute() {
  return (
    <Suspense fallback={null}>
      <ExperimentsPage />
    </Suspense>
  );
}
