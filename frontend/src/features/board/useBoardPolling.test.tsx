import { act, renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import type { BoardData } from "../../api/contracts";
import { api } from "../../api/service";
import { useBoardPolling } from "./useBoardPolling";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function board(runId: string, batchNumber: number): BoardData {
  return {
    project_id: "project",
    run_id: runId,
    batch_number: batchNumber,
    run_archived: false,
    run_status: "completed",
    items: [],
    updated_at: "2026-08-21T00:00:00Z",
  };
}

it("discards a slow old batch response after switching to a new batch", async () => {
  const oldRequest = deferred<BoardData>();
  const newRequest = deferred<BoardData>();
  const getBoard = vi.spyOn(api, "getBoard").mockImplementation((_project, runId) =>
    runId === "run-old" ? oldRequest.promise : newRequest.promise
  );
  const { result, rerender } = renderHook(
    ({ runId }) => useBoardPolling("project", runId),
    { initialProps: { runId: "run-old" } },
  );

  rerender({ runId: "run-new" });
  await waitFor(() => expect(getBoard).toHaveBeenCalledWith("project", "run-new"));
  await act(async () => { newRequest.resolve(board("run-new", 2)); });
  await waitFor(() => expect(result.current.data?.run_id).toBe("run-new"));
  await act(async () => { oldRequest.resolve(board("run-old", 1)); });

  expect(result.current.data?.run_id).toBe("run-new");
  getBoard.mockRestore();
});
