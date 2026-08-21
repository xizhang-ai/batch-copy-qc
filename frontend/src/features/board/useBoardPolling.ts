import { useCallback, useEffect, useRef, useState } from "react";
import type { BoardData } from "../../api/contracts";
import { api } from "../../api/service";

export function useBoardPolling(projectId: string, runId?: string) {
  const [data, setData] = useState<BoardData>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestSequence = useRef(0);
  const refresh = useCallback(async () => {
    const requestId = ++requestSequence.current;
    setLoading(true);
    try {
      const result = await api.getBoard(projectId, runId);
      if (requestId !== requestSequence.current) return;
      setData(result);
      setError("");
    } catch (err) {
      if (requestId === requestSequence.current) setError((err as Error).message);
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }, [projectId, runId]);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible" && data?.run_status === "running") void refresh(); }, 2000);
    return () => {
      window.clearInterval(timer);
      requestSequence.current += 1;
    };
  }, [data?.run_status, refresh]);
  return { data, setData, loading, error, refresh };
}
