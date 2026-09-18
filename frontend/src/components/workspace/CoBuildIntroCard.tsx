"use client";

import Link from "next/link";
import { ArrowRight, HandHeart, Lock, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { withCollectionMode } from "@/lib/collection-mode";

/**
 * Entry screen for the AI co-build programme.  It is a way *into* the ordinary
 * experiment workspace — never a separate form to fill in.
 */
export default function CoBuildIntroCard({
  experimentId,
  experimentName,
}: {
  experimentId: string;
  experimentName: string;
}) {
  const workspace = withCollectionMode(`/experiments/${experimentId}/workspace`, true);

  return (
    <section className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-white to-violet-50 p-6 sm:p-7">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
          <Sparkles className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-500">AI 实验共建模式</p>
          <h2 className="mt-1 text-lg font-extrabold tracking-tight text-stone-900">
            参与 PhysLab AI 实验共建
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-stone-600">
            你的实验过程不会受到影响。在完成实验报告的同时，你可以帮助 PhysLab
            学习真实实验记录，提升未来实验数据识别能力。
          </p>

          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {[
              [HandHeart, "自愿参与", "随时可以退出，不参与也完整可用"],
              [ShieldCheck, "不影响实验完成", "录入、计算、绘图、报告流程完全一致"],
              [Lock, "上传前请脱敏个人信息", "姓名、学号、联系方式请先遮盖或裁掉"],
              [RotateCcw, "可以随时撤回贡献", "撤回后原图与相关训练数据一并删除"],
            ].map(([Icon, title, detail]) => {
              const Component = Icon as typeof HandHeart;
              return (
                <li key={String(title)} className="flex items-start gap-2.5 rounded-xl bg-white/70 p-3">
                  <Component className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
                  <span className="text-xs leading-5 text-stone-600">
                    <span className="font-bold text-stone-800">{String(title)}</span>
                    <br />
                    {String(detail)}
                  </span>
                </li>
              );
            })}
          </ul>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Link
              href={workspace}
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-indigo-700"
            >
              开始共建实验
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href={`/experiments/${experimentId}/workspace`}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-stone-300 bg-white px-5 text-sm font-semibold text-stone-700"
            >
              先按普通模式做实验
            </Link>
            <span className="text-xs text-stone-500">本次将处理：{experimentName}</span>
          </div>
        </div>
      </div>
    </section>
  );
}
