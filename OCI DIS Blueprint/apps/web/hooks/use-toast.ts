"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastKind = "success" | "error" | "info";

export type Toast = {
  id: string;
  kind: ToastKind;
  message: string;
  exiting?: boolean;
};

type ToastListener = (_toast: Toast) => void;

const listeners: Set<ToastListener> = new Set();

export function emitToast(kind: ToastKind, message: string): void {
  const toast: Toast = { id: `${Date.now()}-${Math.random()}`, kind, message };
  listeners.forEach((listener) => listener(toast));
}

export function useToastStack(): {
  toasts: Toast[];
  dismiss: (_toastId: string) => void;
} {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<string, number>>(new Map<string, number>());

  const dismiss = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((previous) => previous.map((toast) => (toast.id === id ? { ...toast, exiting: true } : toast)));
    window.setTimeout(() => {
      setToasts((previous) => previous.filter((toast) => toast.id !== id));
    }, 160);
  }, []);

  useEffect(() => {
    const timerMap: Map<string, number> = timers.current;
    const handler = (toast: Toast) => {
      setToasts((previous) => [...previous.slice(-4), toast]);
      const timer = window.setTimeout(() => dismiss(toast.id), 4000);
      timerMap.set(toast.id, timer);
    };
    listeners.add(handler);
    return () => {
      listeners.delete(handler);
      timerMap.forEach((timer) => window.clearTimeout(timer));
      timerMap.clear();
    };
  }, [dismiss]);

  return { toasts, dismiss };
}
