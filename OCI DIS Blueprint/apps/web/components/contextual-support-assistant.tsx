"use client";

/* Persistent floating support assistant with route-aware governed context. */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Check, Loader2, MessageCircle, Paperclip, Send, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { api, getErrorMessage } from "@/lib/api";
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
  const [conversation, setConversation] = useState<SupportConversation | null>(null);
  const [supportSessionId, setSupportSessionId] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<SupportAttachmentInput[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [conversation?.messages.length, open]);

  function updateOpen(next: boolean): void {
    setOpen(next);
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

  return (
    <div className="fixed bottom-4 right-4 z-[70] sm:bottom-6 sm:right-6">
      {open ? (
        <section
          className="isolate flex h-[min(680px,calc(100vh-32px))] w-[min(430px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[0_24px_80px_rgba(0,0,0,0.38)]"
          role="dialog"
          aria-label="OCI DIS App Assistant"
        >
          <header className="flex items-start gap-3 border-b border-[var(--color-border)] px-4 py-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-accent)] text-white">
              <Bot className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold text-[var(--color-text-primary)]">OCI DIS App Assistant</h2>
              <p className="mt-0.5 truncate text-xs text-[var(--color-text-muted)]">Context: {routeContext.pageTitle}</p>
            </div>
            <button type="button" className="app-icon-button" onClick={() => updateOpen(false)} aria-label="Close App Assistant" title="Close">
              <X className="h-4 w-4" />
            </button>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Loading support session</div>
            ) : conversation?.messages.length ? (
              conversation.messages.map((message) => (
                <article key={message.id} className={message.role === "user" ? "ml-8" : "mr-8"}>
                  <div className={message.role === "user" ? "rounded-xl bg-[var(--color-accent)] px-3.5 py-3 text-sm leading-6 text-white" : "rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3.5 py-3 text-sm leading-6 text-[var(--color-text-primary)]"}>
                    {message.status === "pending" ? (
                      <span className="inline-flex items-center gap-2 text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Reviewing governed context</span>
                    ) : (
                      <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{message.content}</p>
                    )}
                  </div>
                  {message.attachments.length ? <p className="mt-1 text-[10px] text-[var(--color-text-muted)]">Context: {message.attachments.map((item) => item.label).join(", ")}</p> : null}
                  {message.citations.length ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {message.citations.map((citation) => <Link key={`${message.id}-${citation.href}`} href={citation.href} className="app-theme-chip text-[10px]">{citation.label}</Link>)}
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <div>
                <p className="text-sm leading-6 text-[var(--color-text-secondary)]">Ask about the App or the governed architecture evidence in the current view. Unrelated questions are outside this assistant&apos;s scope.</p>
                <div className="mt-4 space-y-2">
                  {routeContext.suggestions.map((suggestion) => (
                    <button key={suggestion} type="button" className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-left text-sm text-[var(--color-text-primary)] transition hover:bg-[var(--color-hover)]" onClick={() => setInput(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            {attachments.length ? (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {attachments.map((item) => (
                  <button key={`${item.attachment_type}-${item.entity_id}-${item.href}`} type="button" onClick={() => setAttachments((current) => current.filter((candidate) => !sameSupportAttachment(candidate, item)))} className="app-theme-chip gap-1 text-[10px]" title="Remove context">
                    <Check className="h-3 w-3" />{item.label}<X className="h-3 w-3" />
                  </button>
                ))}
              </div>
            ) : null}
            {error ? <p className="mb-2 text-xs text-[var(--color-danger)]">{error}</p> : null}
            <form onSubmit={(event) => void submit(event)}>
              <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }} className="min-h-20 w-full resize-none rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-accent)]" placeholder="Ask about this App, integration, topology, or BOM..." maxLength={2000} disabled={sending || pending} aria-label="Ask OCI DIS App Assistant" />
              <div className="mt-2 flex items-center justify-between gap-2">
                <button type="button" className="app-button-secondary gap-2 px-3" onClick={attachCurrentView} disabled={attachments.some((item) => sameSupportAttachment(item, routeContext.attachment))}>
                  {attachments.some((item) => sameSupportAttachment(item, routeContext.attachment)) ? <Check className="h-4 w-4" /> : <Paperclip className="h-4 w-4" />}
                  {attachments.some((item) => sameSupportAttachment(item, routeContext.attachment)) ? "Attached" : "Attach view"}
                </button>
                <button type="submit" className="app-button-primary gap-2 px-3" disabled={!input.trim() || sending || pending}>
                  {sending || pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send
                </button>
              </div>
            </form>
          </footer>
        </section>
      ) : (
        <button type="button" onClick={() => updateOpen(true)} className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-accent)] text-white shadow-[0_12px_32px_rgba(0,0,0,0.28)] transition hover:brightness-110" aria-label="Open OCI DIS App Assistant" title="App Assistant">
          <MessageCircle className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
