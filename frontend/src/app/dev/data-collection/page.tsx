import type { Metadata } from "next";
import DataCollectionDashboard from "@/components/dev/DataCollectionDashboard";

/** Developer-only page: intentionally absent from the public navigation. */
export const metadata: Metadata = {
  title: "Data Collection · 开发者面板",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <DataCollectionDashboard />;
}
