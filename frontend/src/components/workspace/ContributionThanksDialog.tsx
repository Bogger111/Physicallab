"use client";

import { ArrowRight, CheckCircle2, Database, ScanText, Sparkles, Trash2, Wand2 } from "lucide-react";
import type { DataCollectionController } from "@/hooks/useDataCollection";

/**
 * Thank-you dialog shown once a co-built experiment has committed its values.
 * It reports what the contribution improves and how large it was — and offers
 * the withdrawal.  No session id, no path, no internal detail is rendered.
 */
export default function ContributionThanksDialog({
  collection,
  experimentName,
}: {
  collection: DataCollectionController;
  experimentName?: string | null;
}) {
  if (!collection.showThanks) return null;

  const name = collection.experimentName ?? experimentName ?? "本次实验";
  const samples = collection.estimatedSamples;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="感谢参与 PhysLab AI 实验共建"
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4"
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl sm:p-7">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-600 text-white">
            <Sparkles className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h2 className="text-lg font-extrabold tracking-tight text-stone-900">
              感谢参与 PhysLab AI 实验共建！
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-stone-600">
              你的本次实验记录已经帮助优化：
            </p>
          </div>
        </div>

        <ul className="mt-4 space-y-2">
          {[
            [ScanText, "实验数据识别"],
            [Database, "OCR 模型训练"],
            [Wand2, "实验助手能力"],
          ].map(([Icon, label]) => {
            const Component = Icon as typeof ScanText;
            return (
              <li key={String(label)} className="flex items-center gap-2 rounded-xl bg-stone-50 px-3 py-2">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                <Component className="h-4 w-4 shrink-0 text-stone-400" />
                <span className="text-sm font-semibold text-stone-800">{String(label)}</span>
              </li>
            );
          })}
        </ul>

        <div className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-500">本次贡献</p>
          <dl className="mt-2 space-y-1.5 text-sm">
            <div className="flex items-baseline gap-2">
              <dt className="w-14 text-stone-500">实验</dt>
              <dd className="font-bold text-stone-900">{name}</dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="w-14 text-stone-500">生成</dt>
              <dd className="font-bold text-stone-900">
                <span className="text-xl font-extrabold tabular-nums text-indigo-700">
                  {samples ?? "—"}
                </span>{" "}
                个 OCR 数据样本
              </dd>
            </div>
          </dl>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => {
              void collection.withdraw();
            }}
            className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-red-200 bg-white px-4 text-xs font-semibold text-red-700 transition-colors hover:bg-red-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            撤回本次贡献
          </button>
          <button
            type="button"
            onClick={collection.dismissThanks}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-stone-900 px-5 text-sm font-bold text-white"
          >
            继续使用 PhysLab
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-3 text-[11px] leading-5 text-stone-400">
          参与完全自愿；撤回后本次上传的原图与由它生成的数据样本都会被删除。
        </p>
      </div>
    </div>
  );
}
