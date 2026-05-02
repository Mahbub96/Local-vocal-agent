import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../lib/cn";

export type SelectPillProps = {
  id: string;
  /** Accessible name (visually hidden). */
  label: string;
  value: string;
  options: readonly string[];
  onChange?: (value: string) => void;
  icon?: ReactNode;
  className?: string;
  selectClassName?: string;
  /** Native tooltip on `<select>`. */
  title?: string;
};

/** Rounded pill with optional leading icon and styled native `<select>`. */
export function SelectPill({
  id,
  label,
  value,
  options,
  onChange,
  icon,
  className,
  selectClassName,
  title,
}: SelectPillProps) {
  return (
    <>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className={cn("relative inline-flex w-full max-w-full items-center", className)}>
        <div className="relative inline-flex w-full max-w-full items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1.5 sm:inline-flex sm:w-auto sm:max-w-none sm:gap-2 sm:px-3 sm:py-2">
        {icon}
        <select
          id={id}
          title={title}
          className={cn(
            "min-w-0 flex-1 cursor-pointer appearance-none bg-transparent pr-6 text-sm font-medium text-white outline-none ring-0",
            selectClassName,
          )}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
        >
          {options.map((opt) => (
            <option key={opt} value={opt} className="bg-aurora-rail">
              {opt}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-white/40"
          aria-hidden
        />
        </div>
      </div>
    </>
  );
}
