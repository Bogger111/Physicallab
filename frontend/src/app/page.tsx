import Link from "next/link";
import {
  ArrowRight,
  ChevronRight,
  Printer,
  PenLine,
  ChartSpline,
  FlaskConical,
  Clock3,
  Download,
  Sparkles,
} from "lucide-react";
import { experiments } from "@/lib/experiments";

const STEPS = [
  {
    icon: Printer,
    title: "实验前 · 打印",
    desc: "下载标准数据记录表，打印后带入实验室，按格式手写记录。",
  },
  {
    icon: PenLine,
    title: "实验中 · 记录",
    desc: "无需电脑入场，纸笔照常填写，仪器读数零门槛记录。",
  },
  {
    icon: ChartSpline,
    title: "实验后 · 出图",
    desc: "数据录入即自动完成计算、最小二乘拟合与绘图，结果一键导出。",
  },
] as const;

function MalusPreview() {
  // I = I₀·cos²θ sample curve, normalized I₀ = 100
  const pts: [number, number][] = [];
  for (let t = 0; t <= 90; t += 10) {
    pts.push([t, 100 * Math.cos((t * Math.PI) / 180) ** 2]);
  }
  const W = 340;
  const H = 210;
  const padL = 38;
  const padR = 14;
  const padT = 16;
  const padB = 30;
  const x = (deg: number) => padL + (deg / 90) * (W - padL - padR);
  const y = (v: number) => padT + (1 - v / 100) * (H - padT - padB);
  const smooth =
    "M " +
    pts
      .map(([d, v], i) => (i === 0 ? `${x(d)},${y(v)}` : ` C ${x(d - 5)},${y(v)} ${x(d - 5)},${y(v)} ${x(d)},${y(v)}`))
      .join(" ");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="马吕斯定律 I=cos²θ 拟合曲线示意图"
      className="w-full"
    >
      {/* grid */}
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line
          key={`h${f}`}
          x1={padL}
          x2={W - padR}
          y1={padT + (H - padT - padB) * f}
          y2={padT + (H - padT - padB) * f}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="2 4"
        />
      ))}
      {[0, 30, 60, 90].map((d) => (
        <line
          key={`v${d}`}
          x1={x(d)}
          x2={x(d)}
          y1={padT}
          y2={H - padB}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="2 4"
        />
      ))}
      {/* axes */}
      <line x1={padL} x2={padL} y1={padT} y2={H - padB} stroke="rgba(255,255,255,0.28)" />
      <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="rgba(255,255,255,0.28)" />
      {/* theory fit */}
      <path d={smooth} fill="none" stroke="#a5b4fc" strokeWidth="2.4" strokeLinecap="round" />
      {/* data points */}
      {pts.map(([d, v]) => (
        <circle key={d} cx={x(d)} cy={y(v)} r="3.4" fill="#e0e7ff" stroke="#6366f1" strokeWidth="1.6" />
      ))}
      {/* axis labels */}
      <text x={padL} y={H - 8} fill="rgba(255,255,255,0.5)" fontSize="9.5">
        θ / °
      </text>
      <text x={W - 12} y={H - 8} fill="rgba(255,255,255,0.5)" fontSize="9.5" textAnchor="end">
        I ∝ cos²θ
      </text>
    </svg>
  );
}

export default function HomePage() {
  const featured = experiments[0];

  return (
    <div>
      {/* ================= Hero ================= */}
      <section className="relative overflow-hidden bg-hero-glow">
        <div className="pointer-events-none absolute inset-0 bg-dots opacity-60 [mask-image:linear-gradient(to_bottom,black,transparent_70%)]" />
        <div className="container-x relative px-4 pb-24 pt-20 text-center sm:pb-28 sm:pt-24">
          <div className="animate-rise-in inline-flex items-center gap-2 rounded-full border border-stone-200/80 bg-white/80 py-1.5 pl-2 pr-4 text-[13px] font-medium text-stone-600 shadow-sm backdrop-blur">
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-600 px-2 py-0.5 text-[11px] font-semibold text-white">
              <FlaskConical className="h-3 w-3" />
              HUST
            </span>
            华中科技大学 · 大学物理实验
          </div>

          <h1 className="mx-auto mt-7 max-w-3xl text-4xl font-black leading-[1.12] tracking-tight text-stone-900 sm:text-6xl lg:text-[72px]">
            实验结束，
            <br />
            <span className="text-gradient">数据处理也结束。</span>
          </h1>

          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-stone-500 sm:text-lg">
            实验前打印标准数据表，实验后录入原始读数，
            <br className="hidden sm:block" />
            自动完成计算、拟合与出图——从实验台到报告，不到一分钟。
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/experiments"
              className="group inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-8 text-[15px] font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all hover:-translate-y-0.5 hover:bg-indigo-700 hover:shadow-xl hover:shadow-indigo-600/35 sm:w-auto"
            >
              普通实验 · 选择实验，开始处理
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/experiments?mode=collection"
              className="group inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-white/90 px-7 text-[15px] font-semibold text-indigo-700 shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-indigo-300 hover:bg-white sm:w-auto"
            >
              <Sparkles className="h-4 w-4" />
              AI 实验共建
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#workflow"
              className="inline-flex h-12 w-full items-center justify-center gap-1.5 rounded-xl border border-stone-300 bg-white/80 px-7 text-[15px] font-medium text-stone-700 backdrop-blur transition-colors hover:border-stone-400 hover:bg-white sm:w-auto"
            >
              查看工作流程
              <ChevronRight className="h-4 w-4 text-stone-400" />
            </a>
          </div>

          <p className="mx-auto mt-5 max-w-2xl text-xs leading-6 text-stone-500">
            两种模式进入同一个实验工作台：<span className="font-semibold text-stone-700">普通实验</span>不保存任何上传内容；
            <span className="font-semibold text-indigo-700">AI 实验共建</span>在实验完成后额外保存脱敏记录表与确认数据，用于改进数据识别能力，可随时撤回。
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs font-medium text-stone-400">
            <span className="inline-flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" /> 自动计算 · 最小二乘拟合
            </span>
            <span aria-hidden className="hidden h-1 w-1 rounded-full bg-stone-300 sm:block" />
            <span className="inline-flex items-center gap-1.5">
              <Download className="h-3.5 w-3.5 text-indigo-400" /> 结果图像一键导出
            </span>
            <span aria-hidden className="hidden h-1 w-1 rounded-full bg-stone-300 sm:block" />
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="h-3.5 w-3.5 text-indigo-400" /> 全程 30 秒级
            </span>
          </div>
        </div>
      </section>

      {/* ================= Workflow ================= */}
      <section id="workflow" className="border-y border-stone-200/60 bg-white">
        <div className="container-x py-20 sm:py-24">
          <div className="mx-auto mb-14 max-w-xl text-center">
            <p className="mb-3 flex items-center justify-center gap-2.5 text-xs font-bold text-indigo-600">
              <span className="tracking-[0.3em]">WORKFLOW</span>
              <span className="font-normal text-stone-300">/</span>
              <span>三步完成</span>
            </p>
            <h2 className="text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">
              从实验台到出图，全程不超过一分钟
            </h2>
          </div>

          <div className="relative grid gap-5 sm:gap-6 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className="group relative overflow-hidden rounded-2xl border border-stone-200/70 bg-stone-50/50 p-7 transition-all duration-200 hover:-translate-y-1 hover:border-indigo-200 hover:bg-white hover:shadow-lift"
              >
                {/* ghost index */}
                <span
                  aria-hidden
                  className="pointer-events-none absolute -top-3 right-4 select-none text-[84px] font-black leading-none tracking-tighter text-stone-900/[0.045] transition-colors group-hover:text-indigo-600/[0.07]"
                >
                  {i + 1}
                </span>
                <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/25">
                  <step.icon className="h-6 w-6" strokeWidth={1.9} />
                </div>
                <p className="mb-2 text-xs font-bold tracking-[0.18em] text-indigo-600">
                  STEP {String(i + 1).padStart(2, "0")}
                </p>
                <h3 className="mb-2.5 text-lg font-bold text-stone-900">{step.title}</h3>
                <p className="text-sm leading-relaxed text-stone-500">{step.desc}</p>

                {i < STEPS.length - 1 && (
                  <div className="absolute -right-[26px] top-1/2 z-10 hidden h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-stone-200 bg-white text-stone-300 shadow-sm md:flex">
                    <ChevronRight className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= Featured experiment (dark band) ================= */}
      <section className="bg-panel-dark relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-dots-white opacity-40" />
        <div className="pointer-events-none absolute -left-24 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full bg-indigo-500/20 blur-3xl" />
        <div className="container-x relative py-20 sm:py-24">
          <div className="mb-12 text-center">
            <p className="mb-3 flex items-center justify-center gap-2.5 text-xs font-bold text-indigo-300">
              <span className="tracking-[0.3em]">EXPERIMENT LIBRARY</span>
              <span className="font-normal text-indigo-400/40">/</span>
              <span>实验库</span>
            </p>
            <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              可用实验
            </h2>
            <p className="mt-3 text-sm text-indigo-200/70">选择实验，立即开始数据处理</p>
          </div>

          <Link
            href={`/experiments/${featured.id}`}
            className="group mx-auto grid max-w-4xl gap-8 overflow-hidden rounded-3xl border border-white/15 bg-white/[0.07] p-8 backdrop-blur-md transition-all duration-200 hover:border-white/25 hover:bg-white/[0.10] sm:p-10 lg:grid-cols-[1.2fr_1fr] lg:items-center"
          >
            <div>
              <div className="mb-5 flex flex-wrap items-center gap-2.5">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-400/20 px-3 py-1 text-xs font-semibold text-indigo-200 ring-1 ring-inset ring-indigo-300/30">
                  {featured.category}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/70">
                  <Clock3 className="h-3.5 w-3.5" />
                  {featured.processingTime}
                </span>
              </div>
              <h3 className="text-2xl font-extrabold tracking-tight text-white transition-colors group-hover:text-indigo-100 sm:text-3xl">
                {featured.name}
              </h3>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-indigo-100/70">
                {featured.description}——验证马吕斯定律、半波片与四分之一波片的光学特性。
              </p>
              <ul className="mt-5 flex flex-wrap gap-2">
                {featured.subExperiments.map((s) => (
                  <li
                    key={s.id}
                    className="rounded-md bg-white/[0.06] px-2.5 py-1 text-xs font-medium text-white/75 ring-1 ring-inset ring-white/10"
                  >
                    {s.name}
                  </li>
                ))}
              </ul>
              <span className="mt-8 inline-flex h-11 items-center gap-2 rounded-xl bg-white px-6 text-sm font-bold text-indigo-950 shadow-lg shadow-black/20 transition-all group-hover:gap-3 group-hover:shadow-xl">
                开始实验
                <ArrowRight className="h-4 w-4" />
              </span>
            </div>

            {/* decorative fit plot */}
            <div className="rounded-2xl border border-white/12 bg-[#0f0c29]/60 p-5 shadow-2xl shadow-black/30">
              <div className="mb-3 flex items-center justify-between px-1">
                <span className="text-xs font-semibold text-white/85">马吕斯定律拟合</span>
                <span className="flex items-center gap-1.5 text-[10px] font-medium text-white/45">
                  <span className="inline-block h-1.5 w-3 rounded-full bg-indigo-300/90" />
                  I = I₀ cos²θ
                </span>
              </div>
              <MalusPreview />
            </div>
          </Link>

          <p className="mt-8 text-center text-xs text-white/35">
            更多实验（力学 · 热学 · 电磁学 · 近代物理）正在接入，敬请期待
          </p>
        </div>
      </section>

      {/* ================= Footer ================= */}
      <footer className="border-t border-stone-200/70 bg-stone-50">
        <div className="container-x flex flex-col items-center justify-between gap-4 py-10 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600">
              <FlaskConical className="h-3.5 w-3.5 text-white" strokeWidth={2.2} />
            </span>
            <span className="text-sm font-semibold text-stone-700">PhysLab Killer</span>
            <span aria-hidden className="h-3.5 w-px bg-stone-300" />
            <span className="text-xs text-stone-400">大学物理实验数据处理助手</span>
          </div>
          <div className="flex items-center gap-5 text-xs text-stone-400">
            <Link href="/" className="transition-colors hover:text-stone-700">首页</Link>
            <Link href="/experiments" className="transition-colors hover:text-stone-700">实验库</Link>
            <span>© 2026 华中科技大学</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
