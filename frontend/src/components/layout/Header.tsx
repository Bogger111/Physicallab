"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "首页", active: (p: string) => p === "/" },
  { href: "/experiments", label: "实验库", active: (p: string) => p.startsWith("/experiments") },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-stone-200/70 bg-white/85 backdrop-blur-xl">
      <div className="container-x flex h-16 items-center justify-between gap-4">
        {/* Brand */}
        <Link href="/" className="group flex shrink-0 items-center gap-2.5">
          <span className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 shadow-md shadow-indigo-600/30 transition-transform duration-200 group-hover:-translate-y-px group-hover:shadow-lg group-hover:shadow-indigo-600/35">
            <FlaskConical className="h-[18px] w-[18px] text-white" strokeWidth={2.1} />
            <span className="absolute inset-0 bg-gradient-to-t from-white/0 via-white/0 to-white/25" />
          </span>
          <span className="text-[17px] font-extrabold leading-none tracking-tight text-stone-900">
            PhysLab <span className="text-indigo-600">Killer</span>
          </span>
        </Link>

        {/* Nav */}
        <nav className="flex items-center gap-1" aria-label="主导航">
          {NAV.map((item) => {
            const isActive = item.active(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3.5 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-stone-900 font-semibold text-white shadow-sm"
                    : "font-medium text-stone-500 hover:bg-stone-100 hover:text-stone-900"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* CTA */}
        <Link
          href="/experiments/polarization/workspace"
          className="hidden h-9 items-center gap-1.5 rounded-lg bg-stone-900 px-4 text-sm font-semibold text-white shadow-sm transition-all hover:bg-stone-700 hover:shadow-md md:inline-flex"
        >
          开始使用
          <span aria-hidden>→</span>
        </Link>
      </div>
    </header>
  );
}
