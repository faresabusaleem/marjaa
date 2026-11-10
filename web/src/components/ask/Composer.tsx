"use client";

import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef } from "react";
import { useLang, useT } from "../site/LangProvider";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  busy: boolean;
  placeholder: string;
  large?: boolean;
  autoFocus?: boolean;
}

export function Composer({ value, onChange, onSubmit, onStop, busy, placeholder, large, autoFocus }: Props) {
  const t = useT();
  const lang = useLang();
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with the text, up to a limit.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus && matchMedia("(pointer: fine)").matches) ref.current?.focus();
  }, [autoFocus]);

  const canSend = value.trim().length >= 2 && !busy;
  const button = busy ? (
    <button
      type="button"
      onClick={onStop}
      className="inline-flex h-10 shrink-0 items-center gap-2 rounded-md bg-ink px-3.5 text-small font-medium text-bg transition-opacity hover:opacity-85"
    >
      <Square size={13} fill="currentColor" strokeWidth={0} aria-hidden />
      {t.ask.stop}
    </button>
  ) : (
    <button
      type="submit"
      disabled={!canSend}
      className="inline-flex h-10 shrink-0 items-center gap-2 rounded-md bg-accent-fill px-4 text-small font-medium text-on-accent transition-colors hover:bg-accent-fill-hover active:bg-accent-fill-press disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-ink-muted"
    >
      {t.ask.submit}
      <ArrowUp size={16} strokeWidth={2} aria-hidden />
    </button>
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
      className={`rounded-lg border border-line-strong bg-surface transition-colors focus-within:border-brand-sea focus-within:outline focus-within:outline-1 focus-within:outline-brand-sea ${
        large ? "p-3 sm:p-4" : "flex items-end gap-2 p-2 ps-4"
      }`}
    >
      <label htmlFor="question" className="sr-only">
        {t.ask.label}
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={large ? 2 : 1}
        // Follow the interface direction until there is text to read it from.
        dir={value ? "auto" : lang === "ar" ? "rtl" : "ltr"}
        value={value}
        maxLength={1000}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        className={`block w-full min-w-0 resize-none bg-transparent text-ink outline-none focus-visible:outline-none ${
          large ? "min-h-16 text-lead" : "min-h-6 flex-1 py-2 text-body leading-6"
        }`}
      />
      {large ? (
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="hidden text-caption text-ink-muted sm:block">{t.ask.hint}</span>
          <span className="ms-auto">{button}</span>
        </div>
      ) : (
        button
      )}
    </form>
  );
}
