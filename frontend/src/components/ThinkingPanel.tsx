import { useState } from "react";
import { Brain, Check, ChevronDown, Loader2 } from "lucide-react";
import { getStatusLabel } from "../utils/thinkingStatus";
import type { ThinkingStep } from "../types/ui";

type ThinkingPanelProps = {
  thinking: ThinkingStep[];
};

function StepIcon({ kind }: { kind: ReturnType<typeof getStatusLabel> }) {
  if (kind === "done") {
    return (
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/35">
        <Check className="size-3.5" strokeWidth={2.5} />
      </span>
    );
  }
  if (kind === "running") {
    return (
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-sky-500/20 text-sky-300 ring-1 ring-sky-400/35">
        <Loader2 className="size-3.5 animate-spin" strokeWidth={2.5} />
      </span>
    );
  }
  if (kind === "skip") {
    return (
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white/5 text-white/35 ring-1 ring-white/10">
        <span className="text-[10px] font-bold">—</span>
      </span>
    );
  }
  return (
    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white/5 text-white/30 ring-1 ring-white/10">
      <Loader2 className="size-3.5 opacity-50" strokeWidth={2.5} />
    </span>
  );
}

export function ThinkingPanel({ thinking }: ThinkingPanelProps) {
  const [open, setOpen] = useState(false);
  const steps = thinking.slice(0, 5);

  return (
    <section
      className="aurora-glass rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(12,20,44,0.9),rgba(8,13,28,0.92))] p-4 md:p-5"
      aria-label="Thinking process"
    >
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-tight text-white">
        <Brain className="size-[18px] shrink-0 text-[#00d2ff]/90" strokeWidth={2} aria-hidden />
        Thinking Process
      </h3>
      <ul className="space-y-0 divide-y divide-white/8 overflow-hidden rounded-2xl border border-white/8 bg-[#0b1226]/60">
        {steps.map((step) => {
          const k = getStatusLabel(step.status);
          const sub =
            step.detail ||
            (k === "running"
              ? "Working..."
              : k === "pending"
                ? "Queued"
                : k === "skip"
                  ? "Skipped for this request."
                  : "Done.");
          return (
            <li key={step.key} className="flex gap-3 px-3 py-3">
              <StepIcon kind={k} />
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium leading-snug ${k === "pending" ? "text-white/45" : "text-white/90"}`}>
                  {step.label}
                </p>
                <p
                  className={`mt-0.5 text-xs leading-relaxed text-white/45 ${step.detail ? "italic" : ""}`}
                >
                  {sub}
                </p>
              </div>
            </li>
          );
        })}
        {steps.length === 0 ? (
          <li className="px-3 py-4 text-sm text-white/45">Waiting for session activity.</li>
        ) : null}
      </ul>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mt-3 flex w-full items-center justify-center gap-1 rounded-xl border border-white/12 bg-white/3 py-2 text-xs font-medium text-white/70 transition hover:border-white/20 hover:bg-white/6 hover:text-white/90"
        aria-expanded={open}
      >
        View Details
        <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={2} />
      </button>
      {open ? (
        <pre className="mt-3 max-h-40 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 text-[11px] leading-relaxed text-white/55">
          {JSON.stringify(thinking, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
