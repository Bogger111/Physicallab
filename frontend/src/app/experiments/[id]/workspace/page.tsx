import { experiments } from "@/lib/experiments";
import ExperimentWorkspaceClient from "./client-page";

export function generateStaticParams() {
  return experiments.map(({ id }) => ({ id }));
}

export default function ExperimentWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ExperimentWorkspaceClient params={params} />;
}
