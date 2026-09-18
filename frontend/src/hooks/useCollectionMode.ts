"use client";

import { useSearchParams } from "next/navigation";

import { isCollectionMode } from "@/lib/collection-mode";

/** Reads the AI co-build flag from the current URL. */
export function useCollectionMode(): boolean {
  return isCollectionMode(useSearchParams());
}
