"use client";

import { Database, Loader2, ShieldCheck, Trash2, Upload } from "lucide-react";
import type { DataCollectionController } from "@/hooks/useDataCollection";

export default function DataContributionPanel({ collection }: { collection: DataCollectionController }) {
  if (!collection.enabled) return null;

  const uploaded = collection.state === "pending" || collection.state === "confirmed";
  return (
    <section className="mb-6 rounded-2xl border border-sky-200 bg-sky-50/60 p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-700 text-white">
          <Database className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-stone-900">自愿贡献匿名原始记录表</h2>
          <p className="mt-1 text-xs leading-5 text-stone-600">
            此项完全自愿，默认关闭。拒绝或不上传不会影响手动输入、OCR、计算、验证和报告下载。
            原图只在你主动确认后上传；最终数值只在报告成功生成后保存。
          </p>
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
            上传前请自行裁掉或遮盖姓名、学号、电话、微信、面部、证件及其他个人信息。
            当前版本保存整张已处理图片，不做单元格裁剪，也不会训练 OCR 模型。
          </div>

          {!uploaded ? (
            <div className="mt-4 space-y-3">
              <label className="flex items-start gap-2 text-xs text-stone-700">
                <input
                  type="checkbox"
                  checked={collection.consent}
                  onChange={(event) => collection.setConsent(event.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-stone-300"
                />
                <span>我确认图片已去除个人信息，并同意将原图与本次最终确认数值用于改进表格识别研究。</span>
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 text-xs font-semibold text-stone-700">
                  <Upload className="h-4 w-4" />
                  {collection.file ? collection.file.name : "选择原始记录表"}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
                    className="sr-only"
                    onChange={(event) => collection.setFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <button
                  type="button"
                  disabled={!collection.consent || !collection.file || collection.state === "uploading"}
                  onClick={() => void collection.upload()}
                  className="inline-flex h-9 items-center gap-2 rounded-lg bg-sky-700 px-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {collection.state === "uploading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                  确认并上传
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-white px-3 py-2.5">
              <p className="text-xs text-emerald-800">
                {collection.state === "confirmed"
                  ? `最终数据已确认（修订 ${collection.revision}）；再次生成报告会更新为最新值。`
                  : "原图已保存，等待你成功生成报告后确认最终数值。"}
              </p>
              <button
                type="button"
                onClick={() => void collection.withdraw()}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-700"
              ><Trash2 className="h-3.5 w-3.5" />撤回并删除</button>
            </div>
          )}
          {collection.error && <p role="alert" className="mt-2 text-xs text-red-700">{collection.error}；实验功能不受影响。</p>}
        </div>
      </div>
    </section>
  );
}
