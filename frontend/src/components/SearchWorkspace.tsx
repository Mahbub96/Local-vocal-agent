import { useCallback, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { USER_ID, apiGet } from "../services/api";
import type {
  FileSearchResponse,
  MemorySearchResponse,
} from "../types/ui";

type SearchWorkspaceProps = {
  activeSessionId: string;
  defaultMode?: "memory" | "files";
};

export function SearchWorkspace({
  activeSessionId,
  defaultMode = "memory",
}: SearchWorkspaceProps) {
  const [mode, setMode] = useState<"memory" | "files">(defaultMode);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [memoryMatches, setMemoryMatches] = useState<
    MemorySearchResponse["matches"]
  >([]);
  const [fileMatches, setFileMatches] = useState<FileSearchResponse["matches"]>(
    [],
  );

  const runSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError("");
    try {
      if (mode === "memory") {
        const params = new URLSearchParams({ query: q, user_id: USER_ID, top_k: "8" });
        if (activeSessionId) params.set("session_id", activeSessionId);
        const data = await apiGet<MemorySearchResponse>(
          `/memory/search?${params.toString()}`,
        );
        setMemoryMatches(data.matches);
      } else {
        const params = new URLSearchParams({ query: q, limit: "60" });
        const data = await apiGet<FileSearchResponse>(
          `/files/search?${params.toString()}`,
        );
        setFileMatches(data.matches);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [query, mode, activeSessionId]);

  const resultCount = useMemo(
    () => (mode === "memory" ? memoryMatches.length : fileMatches.length),
    [mode, memoryMatches.length, fileMatches.length],
  );

  return (
    <section className="aurora-glass flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">Search Workspace</h3>
          <p className="text-xs text-white/50">
            {mode === "memory"
              ? "Search semantic memory for this user/session."
              : "Search text across project files."}
          </p>
        </div>
        <div className="flex rounded-xl border border-white/10 bg-white/3 p-1 text-xs">
          <button
            type="button"
            onClick={() => setMode("memory")}
            className={`rounded-lg px-2 py-1 ${mode === "memory" ? "bg-white/12 text-white" : "text-white/55 hover:text-white/90"}`}
          >
            Memory
          </button>
          <button
            type="button"
            onClick={() => setMode("files")}
            className={`rounded-lg px-2 py-1 ${mode === "files" ? "bg-white/12 text-white" : "text-white/55 hover:text-white/90"}`}
          >
            Files
          </button>
        </div>
      </div>

      <div className="mb-3 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void runSearch();
          }}
          placeholder={mode === "memory" ? "Ask from memory..." : "Search in files..."}
          className="h-11 min-w-0 flex-1 rounded-xl border border-white/12 bg-black/30 px-3 text-sm text-white outline-none ring-aurora-cyan/25 focus:ring-2"
        />
        <button
          type="button"
          onClick={() => void runSearch()}
          disabled={loading || !query.trim()}
          className="inline-flex h-11 items-center gap-2 rounded-xl border border-cyan-300/25 bg-cyan-400/10 px-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/16 disabled:opacity-50"
        >
          <Search className="size-4" />
          Search
        </button>
      </div>

      <div className="mb-2 text-xs text-white/55">
        {loading ? "Searching..." : `${resultCount} result(s)`}
      </div>
      {error ? (
        <p className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
          {error}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
        {mode === "memory"
          ? memoryMatches.map((m) => (
              <article
                key={m.message_id}
                className="rounded-xl border border-white/10 bg-white/3 px-3 py-2.5"
              >
                <div className="mb-1 flex flex-wrap gap-2 text-[11px] text-white/45">
                  <span className="uppercase text-cyan-200/80">{m.role}</span>
                  <span>score: {m.score.toFixed(3)}</span>
                  <span>session: {m.session_id.slice(0, 8)}...</span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-white/88">
                  {m.content}
                </p>
              </article>
            ))
          : fileMatches.map((m, idx) => (
              <article
                key={`${m.path}:${m.line_number}:${idx}`}
                className="rounded-xl border border-white/10 bg-white/3 px-3 py-2.5"
              >
                <div className="mb-1 text-[11px] text-cyan-200/80">
                  {m.path}:{m.line_number}
                </div>
                <p className="whitespace-pre-wrap text-sm text-white/88">
                  {m.line}
                </p>
              </article>
            ))}
      </div>
    </section>
  );
}
