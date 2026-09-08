"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, ArrowRight, Clock } from "lucide-react";
import { experiments, categories } from "@/lib/experiments";

export default function ExperimentsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("全部");

  const filtered = experiments.filter((exp) => {
    const matchSearch =
      !search ||
      exp.name.includes(search) ||
      exp.description.includes(search);
    const matchCategory = category === "全部" || exp.category === category;
    return matchSearch && matchCategory;
  });

  return (
    <div className="animate-in mx-auto max-w-4xl px-6 py-16">
      <div className="mb-10">
        <h1 className="mb-3 text-3xl font-bold tracking-tight text-gray-900">
          实验库
        </h1>
        <p className="text-base text-gray-400">选择实验开始数据处理</p>
      </div>

      {/* Search + Filter */}
      <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-300" />
          <input
            type="text"
            placeholder="搜索实验..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-11 w-full rounded-xl border border-gray-200 bg-white pl-11 pr-4 text-sm text-gray-900 outline-none transition-all placeholder:text-gray-300 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                category === cat
                  ? "bg-blue-600 text-white shadow-sm shadow-blue-600/20"
                  : "border border-gray-200 bg-white text-gray-400 hover:border-gray-300 hover:text-gray-600"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Experiment Cards */}
      <div className="grid gap-5 sm:grid-cols-2">
        {filtered.map((exp) => (
          <Link
            key={exp.id}
            href={`/experiments/${exp.id}`}
            className="group block rounded-2xl border border-gray-100 bg-white p-7 transition-all hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50"
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="inline-flex items-center rounded-lg bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                {exp.category}
              </span>
              <span className="flex items-center gap-1.5 text-xs text-gray-300">
                <Clock className="h-3.5 w-3.5" />
                {exp.processingTime}
              </span>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
              {exp.name}
            </h3>
            <p className="mb-6 text-sm text-gray-400 leading-relaxed line-clamp-2">
              {exp.description}
            </p>
            <div className="flex items-center gap-2 text-sm font-medium text-blue-600">
              开始实验
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </div>
          </Link>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="py-24 text-center text-gray-300">
          未找到匹配的实验
        </div>
      )}
    </div>
  );
}
