"use client";

import { CheckCircle2, Database, Loader2, Lock, ShieldCheck, Trash2, Upload, UserCheck } from "lucide-react";
import type { DataCollectionController } from "@/hooks/useDataCollection";
import { useCollectionMode } from "@/hooks/useCollectionMode";
import ContributionThanksDialog from "./ContributionThanksDialog";

/**
 * Voluntary record-sheet contribution, shown only inside the AI co-build entry
 * (`?mode=collection`).  In the ordinary entry the panel renders nothing at all,
 * so no session, image or field data is ever created for a normal experiment.
 *
 * The panel is informational: it never feeds the workbench, the calculation
 * chain or the report.
 *
 * After a successful upload it shows a contribution card — what was saved, what
 * happens next and how many OCR training samples this session can produce.  No
 * storage path and no internal identifier beyond a short, human-sized reference
 * is ever rendered.
 */
export default function DataContributionPanel({
  collection,
  experimentName,
}: {
  collection: DataCollectionController;
  /** Fallback label when the API has not answered yet. */
  experimentName?: string;
}) {
  const collectionMode = useCollectionMode();
  if (!collection.enabled || !collectionMode) return null;

  const uploaded = collection.state === "pending" || collection.state === "confirmed";
  const name = collection.experimentName ?? experimentName ?? "本次实验";
  const reference = collection.sessionId ? collection.sessionId.slice(0, 8) : null;

  return (
    <>
      <ContributionThanksDialog collection={collection} experimentName={experimentName} />
      <section className="mb-6 rounded-2xl border border-sky-200 bg-sky-50/60 p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-700 text-white">
          <Database className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-stone-900">自愿贡献匿名原始记录表</h2>
          <p className="mt-1 text-xs leading-5 text-stone-600">
            此项完全自愿，默认关闭。拒绝或不上传不会影响手动输入、OCR、计算、验证和报告下载。
            原图只在你主动确认后上传；最终数值只在报告成功生成后保存。
          </p>
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
            上传前请自行裁掉或遮盖姓名、学号、电话、微信、面部、证件及其他个人信息。
            图片会在保存前重新编码，自动去除 EXIF 拍摄信息。
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
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-stone-500">
                <li className="inline-flex items-center gap-1"><UserCheck className="h-3.5 w-3.5" />自愿参与，随时可撤回</li>
                <li className="inline-flex items-center gap-1"><Lock className="h-3.5 w-3.5" />已做脱敏处理（去 EXIF、不存账号信息）</li>
                <li className="inline-flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5" />不用于识别任何个人</li>
              </ul>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-white p-4">
              <p className="text-sm font-bold text-emerald-800">感谢参与 PhysLab 数据共建！</p>

              <dl className="mt-3 space-y-2 text-xs">
                <div className="flex flex-wrap items-baseline gap-2">
                  <dt className="w-16 shrink-0 text-stone-500">实验类型</dt>
                  <dd className="font-semibold text-stone-800">{name}</dd>
                </div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <dt className="w-16 shrink-0 text-stone-500">状态</dt>
                  <dd className="inline-flex items-center gap-1.5 font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    图片已安全保存（已脱敏处理）
                  </dd>
                </div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <dt className="w-16 shrink-0 text-stone-500">后续</dt>
                  <dd className="inline-flex items-center gap-1.5 font-semibold text-stone-700">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    {collection.state === "confirmed"
                      ? "已生成 OCR 训练样本"
                      : "数据确认后生成 OCR 训练样本"}
                  </dd>
                </div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <dt className="w-16 shrink-0 text-stone-500">当前贡献</dt>
                  <dd className="font-semibold text-stone-800">
                    预计生成{" "}
                    <span className="text-base font-extrabold text-sky-700 tabular-nums">
                      {collection.estimatedSamples ?? "—"}
                    </span>{" "}
                    个 OCR 样本
                    {collection.state === "pending" && (
                      <span className="ml-1 font-normal text-stone-500">（确认实验数据后生效）</span>
                    )}
                  </dd>
                </div>
                {reference && (
                  <div className="flex flex-wrap items-baseline gap-2">
                    <dt className="w-16 shrink-0 text-stone-500">贡献编号</dt>
                    <dd className="font-mono text-[11px] text-stone-600">{reference}</dd>
                  </div>
                )}
              </dl>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-stone-100 pt-3">
                <p className="text-[11px] leading-5 text-stone-500">
                  {collection.state === "confirmed"
                    ? `已确认实验数据（修订 ${collection.revision}）；再次生成报告会更新为最新值。`
                    : "等你成功生成报告后，本次确认的实验数据会一并保存为该记录表的标签。"}
                  <br />
                  贡献完全自愿，随时可以撤回删除；是否参与不影响任何实验功能。
                </p>
                <button
                  type="button"
                  onClick={() => void collection.withdraw()}
                  className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 text-xs font-semibold text-red-700 transition-colors hover:bg-red-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />撤回贡献
                </button>
              </div>
            </div>
          )}

          {collection.error && <p role="alert" className="mt-2 text-xs text-red-700">{collection.error}；实验功能不受影响。</p>}
        </div>
      </div>
    </section>
    </>
  );
}
