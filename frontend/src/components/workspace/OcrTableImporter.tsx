"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Crop,
  ImagePlus,
  Loader2,
  ScanLine,
  X,
} from "lucide-react";
import { recognizeTableImage, submitOCRFeedback, trackEvent, type OCRCandidate } from "@/lib/api";
import { cropFromPoints, cropImageFile, isUsableCrop, type NormalizedCrop } from "@/lib/image-crop";
import { cn } from "@/lib/utils";

interface Props {
  experimentId: string;
  tableId: string;
  expectedCellCount: number;
  onApply: (values: string[], overwriteExisting: boolean) => void;
}

interface ReviewCell {
  value: string;
  prediction: string;
  rawText: string;
  confidence: number | null;
}

function reviewCells(candidates: OCRCandidate[], count: number): ReviewCell[] {
  return Array.from({ length: count }, (_, index) => {
    const candidate = candidates[index];
    return candidate
      ? { value: candidate.value, prediction: candidate.value, rawText: candidate.raw_text, confidence: candidate.confidence }
      : { value: "", prediction: "", rawText: "", confidence: null };
  });
}

export default function OcrTableImporter({
  experimentId,
  tableId,
  expectedCellCount,
  onApply,
}: Props) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [cells, setCells] = useState<ReviewCell[]>([]);
  const [detectedCount, setDetectedCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overwrite, setOverwrite] = useState(false);
  const [applied, setApplied] = useState(false);
  const [consent, setConsent] = useState(false);
  const [ocrProvider, setOcrProvider] = useState("unknown");
  const [ocrModelVersion, setOcrModelVersion] = useState("unknown");
  const [crop, setCrop] = useState<NormalizedCrop | null>(null);
  const [dragOrigin, setDragOrigin] = useState<{ x: number; y: number } | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const preview = useMemo(() => file ? URL.createObjectURL(file) : null, [file]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const recognized = useMemo(() => cells.filter((cell) => cell.value.trim()).length, [cells]);
  const lowConfidence = useMemo(
    () => cells.filter((cell) => cell.value.trim() && cell.confidence !== null && cell.confidence < 0.75).length,
    [cells]
  );

  const resetRecognition = () => {
    setCells([]);
    setDetectedCount(0);
    setError(null);
    setApplied(false);
  };

  const chooseFile = (next: File | null) => {
    setFile(next);
    resetRecognition();
    setConsent(false);
    setCrop(null);
    setDragOrigin(null);
    setPreviewReady(false);
  };

  const pointerPosition = (event: ReactPointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    };
  };

  const startCrop = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!previewReady || loading) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointerPosition(event);
    resetRecognition();
    setDragOrigin(point);
    setCrop(cropFromPoints(point, point));
  };

  const updateCrop = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragOrigin || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
    event.preventDefault();
    setCrop(cropFromPoints(dragOrigin, pointerPosition(event)));
  };

  const finishCrop = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragOrigin) return;
    event.preventDefault();
    const next = cropFromPoints(dragOrigin, pointerPosition(event));
    setCrop(isUsableCrop(next) ? next : null);
    setDragOrigin(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const runOCR = async () => {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    setApplied(false);
    void trackEvent("ocr_upload", experimentId, { table_id: tableId });
    try {
      const cropped = isUsableCrop(crop);
      const uploadFile = cropped && imageRef.current
        ? await cropImageFile(file, crop, imageRef.current)
        : file;
      const result = await recognizeTableImage(uploadFile, experimentId, tableId);
      setCells(reviewCells(result.candidates, expectedCellCount));
      setDetectedCount(result.candidates.length);
      setOcrProvider(result.ocr_provider ?? "unknown");
      setOcrModelVersion(result.ocr_model_version ?? "unknown");
      void trackEvent("ocr_success", experimentId, {
        table_id: tableId,
        candidate_count: result.candidates.length,
        cropped,
      });
      if (!result.candidates.length) {
        setError("没有识别到数值。请裁剪到数据区域、保持画面水平并提高光线后重试。");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "OCR 识别失败");
      void trackEvent("ocr_failure", experimentId, { table_id: tableId });
    } finally {
      setLoading(false);
    }
  };

  const apply = () => {
    onApply(cells.map((cell) => cell.value.trim()), overwrite);
    setApplied(true);
    void trackEvent("ocr_confirm", experimentId, { table_id: tableId, confirmed_cells: recognized });
    if (consent) {
      cells.forEach((cell, index) => {
        const confirmed = cell.value.trim();
        if (!confirmed) return;
        void submitOCRFeedback({
          sample_id: typeof crypto?.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${index}`,
          experiment_id: experimentId,
          field_id: `${tableId}[${index}]`,
          prediction: cell.prediction,
          confidence: cell.confidence,
          confirmed_value: confirmed,
          was_corrected: cell.prediction !== confirmed,
          verified: true,
          consent: true,
          ocr_provider: ocrProvider,
          ocr_model_version: ocrModelVersion,
        });
        if (cell.prediction !== confirmed) {
          void trackEvent("ocr_corrected", experimentId, { table_id: tableId });
        }
      });
    }
  };

  const removeCell = (index: number) => {
    setCells((previous) => {
      const next = previous.filter((_, itemIndex) => itemIndex !== index);
      while (next.length < expectedCellCount) {
        next.push({ value: "", prediction: "", rawText: "", confidence: null });
      }
      return next.slice(0, expectedCellCount);
    });
  };

  return (
    <div className="mb-3 rounded-xl border border-dashed border-indigo-200 bg-indigo-50/45">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-bold text-indigo-900">
          <Camera className="h-4 w-4 text-indigo-600" />
          图片识别录入
        </span>
        <span className="text-xs font-medium text-indigo-500">{open ? "收起" : "上传手写表格"}</span>
      </button>

      {open && (
        <div className="border-t border-indigo-100 px-4 py-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div>
              {preview ? (
                <div className="rounded-xl border border-indigo-200 bg-white p-3">
                  <div
                    className="relative mx-auto w-fit max-w-full touch-none select-none overflow-hidden rounded-lg bg-stone-100 cursor-crosshair"
                    onPointerDown={startCrop}
                    onPointerMove={updateCrop}
                    onPointerUp={finishCrop}
                    onPointerCancel={finishCrop}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      ref={imageRef}
                      src={preview}
                      alt="待裁剪表格预览"
                      draggable={false}
                      onLoad={() => setPreviewReady(true)}
                      onError={() => {
                        setPreviewReady(false);
                        setCrop(null);
                        setError("当前图片格式无法在浏览器预览，可直接使用整张图片识别或改用 JPG、PNG。")
                      }}
                      className="block max-h-72 max-w-full object-contain"
                    />
                    {isUsableCrop(crop) && (
                      <div
                        aria-label="OCR 裁剪区域"
                        className="pointer-events-none absolute border-2 border-amber-300 shadow-[0_0_0_9999px_rgb(15_23_42/0.48)]"
                        style={{
                          left: `${crop.x * 100}%`,
                          top: `${crop.y * 100}%`,
                          width: `${crop.width * 100}%`,
                          height: `${crop.height * 100}%`,
                        }}
                      >
                        <span className="absolute -left-0.5 -top-0.5 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-amber-400" />
                        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-amber-400" />
                        <span className="absolute -bottom-0.5 -left-0.5 h-2.5 w-2.5 -translate-x-1/2 translate-y-1/2 rounded-full border border-white bg-amber-400" />
                        <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 translate-x-1/2 translate-y-1/2 rounded-full border border-white bg-amber-400" />
                      </div>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="inline-flex items-center gap-1.5 text-stone-500">
                      <Crop className="h-3.5 w-3.5 text-indigo-500" />
                      {isUsableCrop(crop)
                        ? `已框选 ${Math.round(crop.width * 100)}% × ${Math.round(crop.height * 100)}%，拖动可重新框选`
                        : "在图片上拖动，框选需要识别的数据区域"}
                    </span>
                    {isUsableCrop(crop) && (
                      <button
                        type="button"
                        onClick={() => {
                          setCrop(null);
                          resetRecognition();
                        }}
                        className="font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        使用整张图片
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-indigo-200 bg-white p-4 text-center transition-colors hover:border-indigo-400">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
                    capture="environment"
                    className="sr-only"
                    onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
                  />
                  <>
                    <ImagePlus className="mb-2 h-7 w-7 text-indigo-500" />
                    <span className="text-sm font-semibold text-stone-700">拍照或选择表格图片</span>
                    <span className="mt-1 text-xs leading-relaxed text-stone-400">上传后可在浏览器中裁剪数据区域</span>
                  </>
                </label>
              )}
              {file && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={runOCR}
                    disabled={loading}
                    className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-xs font-bold text-white disabled:opacity-50"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />}
                    {loading ? "模型识别中…" : isUsableCrop(crop) ? "识别裁剪区域" : "识别整张图片"}
                  </button>
                  <label className="inline-flex h-9 cursor-pointer items-center justify-center rounded-lg border border-stone-200 bg-white px-3 text-xs font-semibold text-stone-600 hover:border-indigo-300">
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
                      capture="environment"
                      className="sr-only"
                      onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
                    />
                    重新选择
                  </label>
                  <button
                    type="button"
                    onClick={() => chooseFile(null)}
                    className="inline-flex h-9 items-center justify-center rounded-lg border border-stone-200 bg-white px-3 text-stone-500"
                    aria-label="移除图片"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
              <p className="mt-2 text-[11px] leading-relaxed text-stone-400">
                裁剪在浏览器本地完成，仅将框选区域发送到本站 OCR 服务。模型结果必须在右侧复核后才能填入。
              </p>
            </div>

            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-bold text-stone-600">识别校对 · 按纸面从左到右、从上到下</p>
                {!!cells.length && (
                  <span className="text-[11px] text-stone-400">
                    {recognized}/{expectedCellCount} 格{lowConfidence ? ` · ${lowConfidence} 格需重点检查` : ""}
                  </span>
                )}
              </div>
              {cells.length ? (
                <>
                  <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3">
                    {cells.map((cell, index) => {
                      const low = cell.confidence !== null && cell.confidence < 0.75;
                      return (
                        <div key={index} className="relative text-[10px] font-semibold text-stone-400">
                          <label htmlFor={`${tableId}-ocr-${index}`}>第 {index + 1} 格</label>
                          {cell.value && (
                            <button
                              type="button"
                              onClick={() => removeCell(index)}
                              className="absolute right-1 top-0 text-stone-300 hover:text-red-500"
                              aria-label={`忽略第 ${index + 1} 个识别值并将后续结果前移`}
                              title="忽略此值，后续结果自动前移"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          )}
                          <input
                            id={`${tableId}-ocr-${index}`}
                            type="number"
                            step="any"
                            value={cell.value}
                            title={cell.rawText ? `模型原文：${cell.rawText}` : "未识别"}
                            onChange={(event) => setCells((previous) => previous.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, value: event.target.value, confidence: null }
                                : item
                            ))}
                            className={cn(
                              "mt-1 h-9 w-full rounded-lg border bg-white px-2 text-right font-mono text-sm text-stone-800 outline-none",
                              low ? "border-amber-300 bg-amber-50" : "border-stone-200 focus:border-indigo-400"
                            )}
                          />
                        </div>
                      );
                    })}
                  </div>
                  {detectedCount > expectedCellCount && (
                    <p className="mt-2 text-xs text-amber-700">模型多识别了 {detectedCount - expectedCellCount} 个数值，请确认图片中没有表头或旁注。</p>
                  )}
                  <p className="mt-2 text-[11px] text-stone-400">若模型把序号、预填值或旁注当成数据，可点单元格右上角 × 忽略，后续识别值会自动前移。</p>
                  <label className="mt-3 flex items-center gap-2 text-xs text-stone-500">
                    <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
                    覆盖表格中已有的手动数据
                  </label>
                  <label className="mt-2 flex items-start gap-2 text-xs leading-relaxed text-stone-500">
                    <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
                    <span>允许将已确认的匿名裁剪单元格用于改进 OCR（不保存整张表格或身份信息）</span>
                  </label>
                  <button
                    type="button"
                    onClick={apply}
                    disabled={!recognized}
                    className="mt-3 inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-stone-900 px-4 text-xs font-bold text-white disabled:opacity-40"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    {applied ? "已填入，可继续手动修改" : "确认并填入当前表格"}
                  </button>
                </>
              ) : (
                <div className="flex min-h-36 items-center justify-center rounded-xl border border-stone-200 bg-white px-5 text-center text-xs leading-relaxed text-stone-400">
                  识别后将在这里逐格显示结果。黄色单元格表示模型置信度较低。
                </div>
              )}
            </div>
          </div>
          {error && (
            <div role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
