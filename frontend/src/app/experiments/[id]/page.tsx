"use client";

import { use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
import { getExperiment } from "@/lib/experiments";

export default function ExperimentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const experiment = getExperiment(id);

  if (!experiment) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-24 text-center">
        <p className="text-gray-400">实验未找到</p>
        <Link href="/experiments" className="mt-4 inline-block text-blue-600">
          返回实验库
        </Link>
      </div>
    );
  }

  return (
    <div className="animate-in mx-auto max-w-3xl px-6 py-10">
      {/* Back */}
      <Link
        href="/experiments"
        className="mb-10 inline-flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" />
        返回实验库
      </Link>

      {/* Header */}
      <div className="mb-12">
        <span className="mb-4 inline-flex items-center rounded-lg bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          {experiment.category}
        </span>
        <h1 className="mb-3 text-4xl font-bold tracking-tight text-gray-900">
          {experiment.name}
        </h1>
        <p className="text-lg text-gray-400 leading-relaxed">
          {experiment.description}
        </p>
      </div>

      {/* Measurements */}
      <div className="mb-10 rounded-2xl border border-gray-100 bg-white p-7">
        <h2 className="mb-5 text-base font-semibold text-gray-900">
          本实验需要记录的数据
        </h2>
        <div className="flex flex-wrap gap-2.5">
          {experiment.measurements.map((m) => (
            <span
              key={m}
              className="inline-flex items-center rounded-lg bg-gray-50 px-4 py-2 text-sm font-mono text-gray-600 border border-gray-100"
            >
              {m}
            </span>
          ))}
        </div>
      </div>

      {/* Download Record Sheet */}
      <div className="mb-10 rounded-2xl border border-blue-100 bg-blue-50/50 p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="mb-1.5 text-base font-semibold text-gray-900">
              实验数据记录表
            </h2>
            <p className="text-sm text-gray-400">
              打印后直接带入实验室填写，实验结束后上传即可完成数据处理。
            </p>
          </div>
          <a
            href={experiment.recordSheet}
            download
            className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-blue-600 px-6 text-sm font-medium text-white shadow-sm shadow-blue-600/20 transition-all hover:bg-blue-700"
          >
            <Download className="h-4 w-4" />
            下载 PDF
          </a>
        </div>
      </div>

      {/* Flow Steps */}
      <div className="mb-12">
        <h2 className="mb-7 text-base font-semibold text-gray-900">
          操作流程
        </h2>
        <div className="flex items-start justify-between gap-3">
          {[
            { num: "01", title: "下载数据表", desc: "打印空白记录表" },
            { num: "02", title: "完成实验", desc: "在实验室填写数据" },
            { num: "03", title: "上传数据", desc: "在线录入实验数据" },
            { num: "04", title: "生成结果", desc: "自动计算与出图" },
          ].map((step, i) => (
            <div key={step.num} className="flex items-start gap-2 flex-1">
              <div className="text-center flex-1">
                <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-sm font-bold text-gray-400">
                  {step.num}
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {step.title}
                </p>
                <p className="mt-1 text-xs text-gray-300">{step.desc}</p>
              </div>
              {i < 3 && (
                <ChevronRight className="mt-3 h-4 w-4 shrink-0 text-gray-200" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Sub-experiments info */}
      <div className="mb-12 rounded-2xl border border-gray-100 bg-white p-7">
        <h2 className="mb-5 text-base font-semibold text-gray-900">
          包含的子实验
        </h2>
        <div className="space-y-4">
          {experiment.subExperiments.map((sub) => (
            <div
              key={sub.id}
              className="flex items-start gap-4 rounded-xl p-4 transition-colors hover:bg-gray-50"
            >
              <div
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${
                  sub.required
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {sub.required ? "必" : "选"}
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">
                  {sub.name}
                </p>
                <p className="mt-0.5 text-sm text-gray-400">
                  {sub.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="text-center pb-8">
        <Link
          href={`/experiments/${id}/workspace`}
          className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-blue-600 px-10 text-base font-medium text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-700 hover:shadow-xl"
        >
          开始数据处理
          <ArrowRight className="h-5 w-5" />
        </Link>
      </div>
    </div>
  );
}
