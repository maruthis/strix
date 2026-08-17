import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const variants = {
    primary: "bg-white text-black hover:bg-white/90 disabled:bg-white/40",
    secondary: "bg-[rgba(255,255,255,0.06)] text-white border border-[#2a2a2a] hover:bg-[rgba(255,255,255,0.1)]",
    danger: "bg-red-600 text-white hover:bg-red-500 disabled:bg-red-900",
    ghost: "text-[#888] hover:text-white hover:bg-[rgba(255,255,255,0.06)]",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "w-full rounded-lg border border-[#2a2a2a] bg-black px-3 py-2 text-sm text-white placeholder:text-[#555] outline-none focus:border-[#555]",
        props.className
      )}
    />
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(
        "w-full rounded-lg border border-[#2a2a2a] bg-black px-3 py-2 text-sm text-white placeholder:text-[#555] outline-none focus:border-[#555]",
        props.className
      )}
    />
  );
}

export function Select({
  value,
  onChange,
  options,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "rounded-lg border border-[#2a2a2a] bg-black px-3 py-2 text-sm text-white outline-none focus:border-[#555]",
        className
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-40",
        checked ? "bg-white" : "bg-[#2a2a2a]"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 h-5 w-5 rounded-full transition-transform",
          checked ? "translate-x-5 bg-black" : "translate-x-0.5 bg-[#888]"
        )}
      />
    </button>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="mb-4 block">
      <div className="mb-1.5 text-sm font-medium text-white">{label}</div>
      {children}
      {hint && <div className="mt-1 text-xs text-[#666]">{hint}</div>}
    </label>
  );
}
