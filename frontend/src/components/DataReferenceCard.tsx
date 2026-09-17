"use client";

import { useState } from "react";
import { BarChart3, ChevronDown, Info } from "lucide-react";
import type { DataReference } from "@/lib/experiments";
import { cn } from "@/lib/utils";

/**
 * "数据特征参考" card: shows what one experiment's measurements typically look
 * like, so a student knows the magnitude, the spacing between points and the
 * expected shape *before* starting.  Purely informational — it never feeds the
 * workbench inputs or the calculation chain.
 */
export default function DataReferenceCard({
  dataReference,
  className,
}: {
  dataReference: DataReference;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const entries = dataReference.data_reference;
  const collapsedCount = 3;
  const visible = expanded ? entries : entries.slice(0, collapsedCount);
  const hidden = Math.max(0, entries.length - visible.length);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm sm:p-6",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-stone-900 text-white">
          <BarChart3 className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <h3 className="text-[15px] font-bold text-stone-900">📊 数据特征参考</h3>
          <p className="mt-1 text-xs leading-relaxed text-stone-500">
            列的是这个实验测出来“通常长什么样”：量级、相邻点差多少、趋势是否正常。
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {visible.map((entry) => (
          <div key={entry.name} className="rounded-xl border border-stone-100 bg-stone-50/60 p-3.5">
            <p className="text-[13px] font-bold text-stone-800">{entry.name}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {entry.example.map((value) => (
                <span
                  key={value}
                  className="rounded-lg bg-white px-2 py-1 font-mono text-xs tabular-nums text-stone-700 ring-1 ring-inset ring-stone-200"
                >
                  {value}
                </span>
              ))}
            </div>
            {entry.pattern.length > 0 && (
              <ul className="mt-2.5 space-y-1">
                {entry.pattern.map((line) => (
                  <li key={line} className="flex gap-2 text-xs leading-relaxed text-stone-500">
                    <span aria-hidden className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-indigo-400" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 transition-colors hover:text-indigo-800"
        >
          <ChevronDown className="h-3.5 w-3.5" />
          展开其余 {hidden} 项测量量
        </button>
      )}
      {expanded && entries.length > collapsedCount && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-stone-500 transition-colors hover:text-stone-800"
        >
          <ChevronDown className="h-3.5 w-3.5 rotate-180" />
          收起
        </button>
      )}

      <p className="mt-4 flex items-start gap-1.5 border-t border-stone-100 pt-3 text-[11px] leading-relaxed text-stone-400">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          {dataReference.note}。实际数据随仪器与操作会有偏差；这里只提供量级与形态参考，不会填入你的记录表。
        </span>
      </p>
    </div>
  );
}
