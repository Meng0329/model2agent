// Shared small UI primitives matching the Model2Agent design system.
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Button({
  children, children_: _omit, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { children_?: never }) {
  return <button {...props}>{children}</button>;
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn("m2a-spin inline-block rounded-full border-2 border-border", className)}
      style={{ width: 16, height: 16, borderTopColor: "var(--color-accent)" }}
    />
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "err" | "accent" }) {
  const map: Record<string, string> = {
    neutral: "bg-surface-2 text-subink border-border-soft",
    ok: "bg-ok-weak text-ok border-ok/30",
    err: "bg-err-weak text-err border-err/30",
    accent: "bg-accent-weak text-accent border-accent-border",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", map[tone])}>
      {children}
    </span>
  );
}
