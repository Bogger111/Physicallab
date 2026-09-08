import Link from "next/link";
import {
  ArrowRight,
  Printer,
  Pencil,
  BarChart3,
  ChevronRight,
  FlaskConical,
  Clock,
} from "lucide-react";

export default function HomePage() {
  return (
    <div className="animate-in">
      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Subtle gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-blue-50/40 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-3xl px-6 pt-28 pb-24 text-center">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white/80 px-4 py-2 text-sm text-gray-500 backdrop-blur-sm">
            <span className="h-2 w-2 rounded-full bg-green-500" />
            华中科技大学物理实验
          </div>
          <h1 className="mb-6 text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl lg:text-7xl">
            实验结束，
            <br />
            数据处理也结束。
          </h1>
          <p className="mx-auto mb-12 max-w-xl text-lg text-gray-500 leading-relaxed">
            实验前打印标准数据表，实验后上传数据，
            <br className="hidden sm:block" />
            自动完成计算、拟合与绘图。
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/experiments"
              className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-blue-600 px-8 text-sm font-medium text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-700 hover:shadow-xl hover:shadow-blue-600/25"
            >
              <FlaskConical className="h-4 w-4" />
              选择实验
            </Link>
            <a
              href="#workflow"
              className="inline-flex h-12 items-center gap-2 rounded-xl border border-gray-200 bg-white px-8 text-sm font-medium text-gray-700 transition-all hover:border-gray-300 hover:bg-gray-50"
            >
              查看工作流程
              <ChevronRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>

      {/* Workflow */}
      <section id="workflow" className="mx-auto max-w-4xl px-6 pb-28">
        <div className="mb-14 text-center">
          <h2 className="mb-3 text-2xl font-semibold tracking-tight text-gray-900">
            三步完成数据处理
          </h2>
          <p className="text-base text-gray-400">
            从实验台到出图，全程不超过一分钟
          </p>
        </div>

        <div className="grid gap-8 sm:grid-cols-3">
          {[
            {
              step: "01",
              icon: Printer,
              title: "实验前",
              desc: "下载标准数据记录表，打印后带入实验室填写",
              color: "bg-blue-50 text-blue-600 border-blue-100",
              iconSize: "h-6 w-6",
              boxSize: "h-14 w-14",
            },
            {
              step: "02",
              icon: Pencil,
              title: "实验中",
              desc: "在纸质表格上正常手写记录实验数据",
              color: "bg-amber-50 text-amber-600 border-amber-100",
              iconSize: "h-6 w-6",
              boxSize: "h-14 w-14",
            },
            {
              step: "03",
              icon: BarChart3,
              title: "实验后",
              desc: "录入数据，自动完成计算、拟合与出图",
              color: "bg-green-50 text-green-600 border-green-100",
              iconSize: "h-6 w-6",
              boxSize: "h-14 w-14",
            },
          ].map((item, i) => (
            <div
              key={item.step}
              className="group relative flex flex-col items-center rounded-2xl border border-gray-100 bg-white p-8 text-center transition-all hover:border-gray-200 hover:shadow-lg hover:shadow-gray-100"
            >
              {/* Step number */}
              <div className="mb-5 flex items-center gap-3">
                <div
                  className={`flex ${item.boxSize} items-center justify-center rounded-2xl border ${item.color}`}
                >
                  <item.icon className={item.iconSize} />
                </div>
              </div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-300">
                Step {item.step}
              </div>
              <h3 className="mb-3 text-lg font-semibold text-gray-900">
                {item.title}
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                {item.desc}
              </p>
              {/* Connector arrow */}
              {i < 2 && (
                <div className="absolute -right-4 top-1/2 hidden -translate-y-1/2 sm:block">
                  <ChevronRight className="h-5 w-5 text-gray-200" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Available Experiments */}
      <section className="border-t border-gray-100 bg-gray-50/50">
        <div className="mx-auto max-w-4xl px-6 py-24">
          <div className="mb-12 text-center">
            <h2 className="mb-3 text-2xl font-semibold tracking-tight text-gray-900">
              可用实验
            </h2>
            <p className="text-base text-gray-400">
              选择实验即可开始数据处理
            </p>
          </div>

          <div className="mx-auto max-w-xl">
            <Link
              href="/experiments/polarization"
              className="group block rounded-2xl border border-gray-100 bg-white p-8 transition-all hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50"
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="inline-flex items-center rounded-lg bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  光学
                </span>
                <span className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Clock className="h-3.5 w-3.5" />
                  ~30秒
                </span>
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                偏振光与双折射
              </h3>
              <p className="mb-6 text-sm text-gray-400 leading-relaxed">
                马吕斯定律验证、半波片/四分之一波片特性、圆偏振光分析
              </p>
              <div className="flex items-center gap-2 text-sm font-medium text-blue-600">
                开始实验
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 bg-white">
        <div className="mx-auto max-w-4xl px-6 py-10 text-center text-sm text-gray-300">
          PhysicsLab — 大学物理实验数据处理助手
        </div>
      </footer>
    </div>
  );
}
