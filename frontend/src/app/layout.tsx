import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/layout/Header";
import BetaNotice from "@/components/layout/BetaNotice";

export const metadata: Metadata = {
  title: "PhysLab Killer 2.0 Beta — 大学物理实验助手",
  description:
    "PhysLab Killer：实验前打印标准数据表，实验后上传数据，自动完成计算、拟合与绘图。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">
        <Header />
        <BetaNotice />
        <main>{children}</main>
      </body>
    </html>
  );
}
