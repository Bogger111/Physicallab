"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical } from "lucide-react";

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-100 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 shadow-sm shadow-blue-600/20">
            <FlaskConical className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight text-gray-900">
            PhysicsLab
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          <Link
            href="/"
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              pathname === "/"
                ? "bg-gray-100 text-gray-900"
                : "text-gray-400 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            首页
          </Link>
          <Link
            href="/experiments"
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              pathname.startsWith("/experiments")
                ? "bg-gray-100 text-gray-900"
                : "text-gray-400 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            实验库
          </Link>
        </nav>
      </div>
    </header>
  );
}
