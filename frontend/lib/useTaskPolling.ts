"use client";

/**
 * Generic task-polling hook, shared by every async operation in the app
 * (exports, bulk ingest, report upload). Given a task ID, polls
 * GET /tasks/{id} at a fixed interval until the task reaches SUCCESS or
 * FAILURE, then stops. Callers get back the current status, any
 * progress metadata the task reported, and the final result/error.
 *
 * Usage:
 *   const { status, result, error, isRunning } = useTaskPolling<ExportTaskResult>(taskId);
 */
import { useEffect, useRef, useState } from "react";
import { getTaskStatus } from "./resources";
import type { TaskStatus } from "./types";

const POLL_INTERVAL_MS = 1500;

interface TaskPollingState<T> {
  status: TaskStatus | "IDLE";
  progress: { stage?: string; total?: number } | null;
  result: T | null;
  error: string | null;
  isRunning: boolean;
}

export function useTaskPolling<T = unknown>(taskId: string | null): TaskPollingState<T> {
  const [state, setState] = useState<TaskPollingState<T>>({
    status: "IDLE",
    progress: null,
    result: null,
    error: null,
    isRunning: false,
  });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!taskId) {
      setState({ status: "IDLE", progress: null, result: null, error: null, isRunning: false });
      return;
    }

    setState({ status: "PENDING", progress: null, result: null, error: null, isRunning: true });

    let cancelled = false;

    async function poll() {
      try {
        const res = await getTaskStatus(taskId!);
        if (cancelled) return;

        if (res.status === "SUCCESS") {
          setState({ status: "SUCCESS", progress: null, result: (res.result as T) ?? null, error: null, isRunning: false });
          if (intervalRef.current) clearInterval(intervalRef.current);
        } else if (res.status === "FAILURE") {
          setState({
            status: "FAILURE",
            progress: null,
            result: null,
            error: res.error || "Task failed.",
            isRunning: false,
          });
          if (intervalRef.current) clearInterval(intervalRef.current);
        } else {
          setState((prev) => ({ ...prev, status: res.status, progress: res.progress ?? null, isRunning: true }));
        }
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "FAILURE",
          progress: null,
          result: null,
          error: err instanceof Error ? err.message : "Failed to check task status.",
          isRunning: false,
        });
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll(); // immediate first check, don't wait a full interval
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId]);

  return state;
}
