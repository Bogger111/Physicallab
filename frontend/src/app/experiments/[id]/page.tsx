import { Suspense } from "react";
import { experiments } from "@/lib/experiments";
import ExperimentDetailClient from "./client-page";

export function generateStaticParams() {
  return experiments.map(({ id }) => ({ id }));
}

export default function ExperimentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense fallback={null}>
      <ExperimentDetailClient params={params} />
    </Suspense>
  );
}
