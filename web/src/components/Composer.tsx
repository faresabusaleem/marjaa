"use client";

import { useEffect, useRef } from "react";
import { ArrowUp, Square } from "./Icons";
import { usePrefs } from "./Prefs";

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
  const { t, lang } = usePrefs();
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with the text, up to a limit.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const canSend = value.trim().length >= 2 && !busy;
  const button = busy ? (
    <button
      type="button"
      onClick={onStop}
      className="grid size-9 shrink-0 place-items-center rounded-xl bg-ink text-bg transition-opacity hover:opacity-85"
      aria-label={t.stop}
      title={t.stop}
    >
      <Square size={16} />
    </button>
  ) : (
    <button
      type="submit"
      disabled={!canSend}
      className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-accent-ink transition-opacity hover:opacity-90 disabled:opacity-35"
      aria-label={t.submit}
      title={t.submit}
    >
      <ArrowUp size={18} strokeWidth={2.2} />
    </button>
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
      className={`flex rounded-2xl border border-line bg-surface shadow-card transition-colors focus-within:border-accent-line ${
        large ? "flex-col gap-2 p-3 sm:p-4" : "items-end gap-2 p-2 ps-3.5"
      }`}
    >
      <label htmlFor="question" className="sr-only">
        {placeholder}
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={large ? 2 : 1}
        // Follow the interface direction until there is text to detect from.
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
        className={`block min-w-0 flex-1 resize-none bg-transparent text-ink outline-none placeholder:text-faint ${
          large ? "min-h-14 text-lg leading-7" : "min-h-6 py-1.5 text-base leading-6"
        }`}
      />
      {large ? (
        <div className="flex items-center justify-between gap-3">
          <span className="hidden text-xs text-faint sm:block">{t.hint}</span>
          <span className="ms-auto">{button}</span>
        </div>
      ) : (
        button
      )}
    </form>
  );
}
