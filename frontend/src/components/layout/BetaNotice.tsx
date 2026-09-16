export default function BetaNotice() {
  return (
    <aside
      aria-label="测试版说明"
      className="border-b border-amber-200 bg-amber-50 text-amber-950"
    >
      <div className="container-x flex flex-col gap-1 py-2.5 text-xs leading-relaxed sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <p>
          <strong className="font-bold">公开测试版 2.0 Beta 1</strong>
          <span className="mx-2 text-amber-400" aria-hidden>
            ·
          </span>
          计算流程与合成数据测试已通过；真实实验读数、OCR 结果和最终报告请逐项复核。
        </p>
        <a
          href="https://github.com/Bogger111/Physicallab/issues"
          target="_blank"
          rel="noreferrer"
          className="shrink-0 font-semibold text-amber-900 underline decoration-amber-400 underline-offset-2 hover:text-amber-700"
        >
          提交测试反馈
        </a>
      </div>
    </aside>
  );
}
