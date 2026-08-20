import { useCallback, useEffect, useRef, useState } from "react";
import type { BoardData } from "../../api/contracts";
import { api } from "../../api/service";

export function useBoardPolling(projectId: string) {
  const [data, setData] = useState<BoardData>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try { setData(await api.getBoard(projectId)); setError(""); } catch (err) { setError((err as Error).message); } finally { inFlight.current = false; setLoading(false); }
  }, [projectId]);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible" && data?.run_status === "running") void refresh(); }, 2000);
    return () => window.clearInterval(timer);
  }, [data?.run_status, refresh]);
  return { data, setData, loading, error, refresh };
}
