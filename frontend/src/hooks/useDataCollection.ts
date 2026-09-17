"use client";

import { useCallback, useEffect, useState } from "react";
import {
  commitDataCollectionSession,
  createDataCollectionSession,
  deleteDataCollectionSession,
  fetchDataCollectionStatus,
} from "@/lib/api";

export type ContributionState = "idle" | "uploading" | "pending" | "confirmed" | "error";

export interface DataCollectionController {
  enabled: boolean;
  consent: boolean;
  setConsent: (value: boolean) => void;
  file: File | null;
  setFile: (file: File | null) => void;
  state: ContributionState;
  revision: number;
  error: string | null;
  upload: () => Promise<void>;
  commit: (data: object) => Promise<void>;
  withdraw: () => Promise<void>;
}

export function useDataCollection(experimentId: string): DataCollectionController {
  const [enabled, setEnabled] = useState(false);
  const [templateVersion, setTemplateVersion] = useState("2.0");
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState<ContributionState>("idle");
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchDataCollectionStatus()
      .then((status) => {
        if (!active) return;
        setEnabled(status.enabled);
        setTemplateVersion(status.template_version);
      })
      .catch(() => {
        if (active) setEnabled(false);
      });
    return () => { active = false; };
  }, []);

  const upload = useCallback(async () => {
    if (!enabled || !consent || !file || sessionId) return;
    setState("uploading");
    setError(null);
    try {
      const response = await createDataCollectionSession(experimentId, templateVersion, file);
      setSessionId(response.session_id);
      setRevision(response.revision);
      setState("pending");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "原始记录表上传失败");
      setState("error");
    }
  }, [enabled, consent, file, sessionId, experimentId, templateVersion]);

  const commit = useCallback(async (data: object) => {
    if (!enabled || !consent || !sessionId) return;
    try {
      const response = await commitDataCollectionSession(
        sessionId,
        experimentId,
        templateVersion,
        data,
      );
      setRevision(response.revision);
      setState("confirmed");
      setError(null);
    } catch (reason) {
      // Data contribution is always best-effort and must not turn a successful
      // report download into an experiment failure.
      setError(reason instanceof Error ? reason.message : "确认数据未保存");
      setState("error");
    }
  }, [enabled, consent, sessionId, experimentId, templateVersion]);

  const withdraw = useCallback(async () => {
    if (sessionId) {
      try {
        await deleteDataCollectionSession(sessionId);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "撤回失败");
        return;
      }
    }
    setSessionId(null);
    setConsent(false);
    setFile(null);
    setRevision(0);
    setState("idle");
    setError(null);
  }, [sessionId]);

  return {
    enabled,
    consent,
    setConsent,
    file,
    setFile,
    state,
    revision,
    error,
    upload,
    commit,
    withdraw,
  };
}
