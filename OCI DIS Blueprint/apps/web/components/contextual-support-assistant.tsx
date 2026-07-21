"use client";

/* Persistent floating support assistant with route-aware governed context. */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Bot, Check, Loader2, MessageCircle, Paperclip, Send, Trash2, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { api, getErrorMessage } from "@/lib/api";
import { GovernedNarrative } from "@/components/governed-narrative";
import { deriveSupportRouteContext, sameSupportAttachment } from "@/lib/support-context";
import type { SupportAttachmentInput, SupportConversation } from "@/lib/types";

const SESSION_KEY = "oci-dis-support-session-id";
const OPEN_KEY = "oci-dis-support-open";

function sessionId(): string {
  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem(SESSION_KEY, created);
  return created;
}

export function ContextualSupportAssistant(): JSX.Element {
  const pathname = usePathname();
  const routeContext = useMemo(() => deriveSupportRouteContext(pathname), [pathname]);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [conversation, setConversation] = useState<SupportConversation | null>(null);
  const [supportSessionId, setSupportSessionId] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<SupportAttachmentInput[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const clearCancelRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    setMounted(true);
    const id = sessionId();
    setSupportSessionId(id);
    setOpen(window.localStorage.getItem(OPEN_KEY) === "true");
    void api
      .getOrCreateSupportConversation(id)
      .then(setConversation)
      .catch((caught) => setError(getErrorMessage(caught, "Unable to load App support.")))
      .finally(() => setLoading(false));
  }, []);

  const pending = conversation?.messages.some((message) => message.status === "pending") ?? false;
  const latestMessage = conversation?.messages.at(-1);
  const currentContextAdded = attachments.some((item) => sameSupportAttachment(item, routeContext.attachment));
  const contextLedger = useMemo(() => {
    const state = conversation?.context_state ?? {};
    const items: string[] = [];
    const service = state.active_service as { name?: unknown } | undefined;
    const pattern = state.active_pattern as { name?: unknown } | undefined;
    if (typeof service?.name === "string") items.push(service.name);
    if (typeof pattern?.name === "string") items.push(pattern.name);
    if (typeof state.topic === "string") items.push(state.topic.replaceAll("_", " "));
    return items.slice(0, 3);
  }, [conversation?.context_state]);

  useEffect(() => {
    if (!pending || !conversation || !supportSessionId) return;
    const timer = window.setInterval(() => {
      void api
        .getSupportConversation(conversation.id, supportSessionId)
        .then((next) => {
          setConversation(next);
          if (!next.messages.some((message) => message.status === "pending")) setSending(false);
        })
        .catch(() => undefined);
    }, 1200);
    return () => window.clearInterval(timer);
  }, [conversation, pending, supportSessionId]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [latestMessage?.content, latestMessage?.id, latestMessage?.status, open]);

  useEffect(() => {
    if (open && !loading) inputRef.current?.focus();
  }, [loading, open]);

  useEffect(() => {
    if (clearConfirmOpen) clearCancelRef.current?.focus();
  }, [clearConfirmOpen]);

  useEffect(() => {
    if (!clearConfirmOpen) return;
    function closeConfirmation(event: KeyboardEvent): void {
      if (event.key === "Escape") setClearConfirmOpen(false);
    }
    document.addEventListener("keydown", closeConfirmation);
    return () => document.removeEventListener("keydown", closeConfirmation);
  }, [clearConfirmOpen]);

  function updateOpen(next: boolean): void {
    setOpen(next);
    if (!next) setClearConfirmOpen(false);
    window.localStorage.setItem(OPEN_KEY, String(next));
  }

  function attachCurrentView(): void {
    setAttachments((current) =>
      current.some((item) => sameSupportAttachment(item, routeContext.attachment))
        ? current
        : [...current, routeContext.attachment].slice(-8),
    );
  }

  async function submit(event?: FormEvent): Promise<void> {
    event?.preventDefault();
    const content = input.trim();
    if (!content || !conversation || !supportSessionId || sending || pending) return;
    setSending(true);
    setError(null);
    setInput("");
    try {
      const next = await api.sendSupportMessage(conversation.id, supportSessionId, {
        content,
        route: pathname,
        page_title: routeContext.pageTitle,
        project_id: routeContext.projectId,
        integration_id: routeContext.integrationId,
        attachments,
      });
      setConversation(next);
      setAttachments([]);
    } catch (caught) {
      setInput(content);
      setSending(false);
      setError(getErrorMessage(caught, "Unable to send the support question."));
    }
  }

  async function clearHistory(): Promise<void> {
    if (!conversation || !supportSessionId || clearing || pending) return;
    setClearing(true);
    setError(null);
    try {
      const next = await api.clearSupportConversationHistory(conversation.id, supportSessionId);
      setConversation(next);
      setAttachments([]);
      setInput("");
      setClearConfirmOpen(false);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    } catch (caught) {
      setError(getErrorMessage(caught, "Unable to clear the assistant history."));
    } finally {
      setClearing(false);
    }
  }

  if (!mounted) return <></>;

  return createPortal((
    <div className="fixed bottom-2 right-2 z-[120] sm:bottom-5 sm:right-5">
      {open ? (
        <section
          className="relative isolate flex h-[min(720px,calc(100dvh-16px))] w-[min(460px,calc(100vw-16px))] flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[0_24px_80px_rgba(0,0,0,0.38)] sm:h-[min(720px,calc(100dvh-40px))]"
          role="dialog"
          aria-label="OCI DIS App Assistant"
        >
          <header className="relative z-10 flex min-h-[72px] items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent)] text-white shadow-sm">
              <Bot className="h-[19px] w-[19px]" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-sm font-semibold text-[var(--color-text-primary)]">OCI DIS App Assistant</h2>
              <p className="mt-1 flex min-w-0 items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-trend-up)]" />
                <span className="truncate">General App help · context: {routeContext.pageTitle}</span>
              </p>
            </div>
            <button
              type="button"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-[var(--color-text-muted)] transition hover:border-[var(--color-border)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:opacity-35"
              onClick={() => setClearConfirmOpen(true)}
              disabled={loading || clearing || pending || !conversation?.messages.length}
              aria-label="Clear assistant history"
              title={conversation?.messages.length ? "Clear history" : "No history to clear"}
            >
              <Trash2 className="h-[17px] w-[17px]" />
            </button>
            <button type="button" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-[var(--color-text-muted)] transition hover:border-[var(--color-border)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]" onClick={() => updateOpen(false)} aria-label="Close App Assistant" title="Close">
              <X className="h-[18px] w-[18px]" />
            </button>
          </header>

          {contextLedger.length ? (
            <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Active context</span>
              {contextLedger.map((item) => <span key={item} className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-text-secondary)]">{item}</span>)}
            </div>
          ) : null}

          {clearConfirmOpen ? (
            <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
              <div
                className="w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-2xl"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="clear-assistant-history-title"
                aria-describedby="clear-assistant-history-description"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--color-toast-error-bg)] text-[var(--color-toast-error-text)]">
                  <Trash2 className="h-5 w-5" />
                </span>
                <h3 id="clear-assistant-history-title" className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">
                  Clear assistant history?
                </h3>
                <p id="clear-assistant-history-description" className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                  This removes this browser session’s messages and attached contexts. Governed agent execution records remain available for audit.
                </p>
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    ref={clearCancelRef}
                    type="button"
                    className="app-button-secondary h-10 px-4 text-sm"
                    onClick={() => setClearConfirmOpen(false)}
                    disabled={clearing}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[var(--color-toast-error-text)] px-4 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => void clearHistory()}
                    disabled={clearing}
                  >
                    {clearing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    {clearing ? "Clearing" : "Clear history"}
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-5" aria-live="polite">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Getting your workspace ready</div>
            ) : conversation?.messages.length ? (
              conversation.messages.map((message) => (
                <article key={message.id} className={message.role === "user" ? "ml-10" : "mr-3"}>
                  <div className={message.role === "user" ? "rounded-2xl rounded-br-md bg-[var(--color-accent)] px-3.5 py-3 text-sm leading-6 text-white" : "text-sm leading-6 text-[var(--color-text-primary)]"}>
                    {message.status === "pending" ? (
                      <span className="inline-flex items-center gap-2 text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Looking through the governed context</span>
                    ) : message.role === "assistant" ? (
                      <GovernedNarrative content={message.content} compact />
                    ) : (
                      <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{message.content}</p>
                    )}
                  </div>
                  {message.attachments.length ? <p className="mt-1.5 text-[10px] text-[var(--color-text-muted)]">Context: {message.attachments.map((item) => item.label).join(", ")}</p> : null}
                  {message.citations.length ? (
                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      <span className="mr-0.5 text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">Sources</span>
                      {message.citations.map((citation) => <Link key={`${message.id}-${citation.href}`} href={citation.href} className="inline-flex max-w-full items-center gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-medium text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"><span className="truncate">{citation.label}</span><ArrowUpRight className="h-3 w-3 shrink-0" /></Link>)}
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <div className="pt-2">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)]">Hi. What are you working through?</h3>
                <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Ask anything about OCI DIS Architect. The current view is optional context; add it when you want a record-specific answer.</p>
                <div className="mt-5 space-y-2">
                  {routeContext.suggestions.map((suggestion) => (
                    <button key={suggestion} type="button" className="group flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3.5 py-3 text-left text-sm text-[var(--color-text-primary)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-hover)]" onClick={() => { setInput(suggestion); inputRef.current?.focus(); }}><span>{suggestion}</span><ArrowUpRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)] transition group-hover:text-[var(--color-accent)]" /></button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <footer className="relative z-10 border-t border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            {attachments.length ? (
              <div className="mb-2.5 flex max-h-20 flex-wrap gap-1.5 overflow-y-auto">
                {attachments.map((item) => (
                  <button key={`${item.attachment_type}-${item.entity_id}-${item.href}`} type="button" onClick={() => setAttachments((current) => current.filter((candidate) => !sameSupportAttachment(candidate, item)))} className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-medium text-[var(--color-text-secondary)]" title={`Remove ${item.label} context`}>
                    <Check className="h-3 w-3 shrink-0 text-[var(--color-trend-up)]" /><span className="truncate">{item.label}</span><X className="h-3 w-3 shrink-0" />
                  </button>
                ))}
              </div>
            ) : null}
            {error ? <p className="mb-2 text-xs text-[var(--color-toast-error-text)]">{error}</p> : null}
            <form onSubmit={(event) => void submit(event)}>
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-2 shadow-sm transition focus-within:border-[var(--color-accent)]">
                <textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }} className="max-h-32 min-h-14 w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-6 text-[var(--color-text-primary)] outline-none" placeholder="Ask anything about OCI DIS Architect" maxLength={2000} disabled={sending || pending} aria-label="Ask OCI DIS App Assistant" />
                <div className="mt-1 flex min-h-9 items-center justify-between gap-2">
                  <button type="button" className="inline-flex h-8 min-w-0 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:opacity-60" onClick={attachCurrentView} disabled={currentContextAdded}>
                    {currentContextAdded ? <Check className="h-3.5 w-3.5 shrink-0 text-[var(--color-trend-up)]" /> : <Paperclip className="h-3.5 w-3.5 shrink-0" />}
                    <span className="truncate">{currentContextAdded ? "Context added" : "Add context"}</span>
                  </button>
                  <button type="submit" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent)] text-white transition hover:bg-[var(--color-accent-hover)] disabled:cursor-not-allowed disabled:opacity-40" disabled={!input.trim() || sending || pending} aria-label="Send message" title="Send">
                    {sending || pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </form>
          </footer>
        </section>
      ) : (
        <button type="button" onClick={() => updateOpen(true)} className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-accent)] text-white shadow-[0_12px_32px_rgba(0,0,0,0.28)] transition hover:bg-[var(--color-accent-hover)]" aria-label="Open OCI DIS App Assistant" title="App Assistant">
          <MessageCircle className="h-5 w-5" />
        </button>
      )}
    </div>
  ), document.body);
}
