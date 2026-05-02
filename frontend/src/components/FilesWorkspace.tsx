import { useCallback, useEffect, useMemo, useState } from "react";
import { File, Folder, RefreshCw } from "lucide-react";
import { apiGet } from "../services/api";
import type { FileContentResponse, FileListResponse } from "../types/ui";

export function FilesWorkspace() {
  const [currentPath, setCurrentPath] = useState("");
  const [root, setRoot] = useState("");
  const [entries, setEntries] = useState<FileListResponse["entries"]>([]);
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadDir = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ limit: "300" });
      if (path) q.set("path", path);
      const data = await apiGet<FileListResponse>(`/files?${q.toString()}`);
      setRoot(data.root);
      setCurrentPath(data.current_path || "");
      setEntries(data.entries);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFile = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ path });
      const data = await apiGet<FileContentResponse>(`/files/content?${q.toString()}`);
      setSelectedFilePath(data.path);
      setFileContent(data.content);
    } catch (e) {
      setError(String(e));
      setSelectedFilePath(path);
      setFileContent("");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDir("");
  }, [loadDir]);

  const parentPath = useMemo(() => {
    if (!currentPath) return "";
    const parts = currentPath.split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }, [currentPath]);

  const dirs = entries.filter((e) => e.is_dir);
  const files = entries.filter((e) => !e.is_dir);

  return (
    <section className="aurora-glass flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">Files Workspace</h3>
          <p className="text-xs text-white/50">
            Browse project files and preview text content.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadDir(currentPath)}
          className="inline-flex items-center gap-1 rounded-lg border border-white/12 bg-white/5 px-2 py-1 text-xs text-white/75 transition hover:bg-white/8"
        >
          <RefreshCw className="size-3.5" />
          Refresh
        </button>
      </div>

      <div className="mb-2 rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-xs text-white/55">
        Root: {root || "…"} / {currentPath || "(root)"}
      </div>

      {error ? (
        <p className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
          {error}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <div className="min-h-0 overflow-y-auto rounded-xl border border-white/10 bg-white/3 p-2">
          <div className="mb-2 flex gap-2">
            <button
              type="button"
              disabled={!currentPath}
              onClick={() => void loadDir(parentPath)}
              className="rounded-lg border border-white/12 bg-white/4 px-2 py-1 text-xs text-white/75 disabled:opacity-40"
            >
              .. Parent
            </button>
            <button
              type="button"
              onClick={() => void loadDir("")}
              className="rounded-lg border border-white/12 bg-white/4 px-2 py-1 text-xs text-white/75"
            >
              Root
            </button>
          </div>

          <div className="space-y-1">
            {dirs.map((e) => (
              <button
                key={`d:${e.path}`}
                type="button"
                onClick={() => void loadDir(e.path)}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-white/85 transition hover:bg-white/8"
              >
                <Folder className="size-4 text-cyan-300/90" />
                <span className="truncate">{e.name}</span>
              </button>
            ))}
            {files.map((e) => (
              <button
                key={`f:${e.path}`}
                type="button"
                onClick={() => void loadFile(e.path)}
                className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${
                  selectedFilePath === e.path
                    ? "bg-white/10 text-white"
                    : "text-white/78 hover:bg-white/8"
                }`}
              >
                <File className="size-4 text-white/55" />
                <span className="truncate">{e.name}</span>
              </button>
            ))}
            {!entries.length && !loading ? (
              <p className="px-2 py-1 text-xs text-white/45">No entries.</p>
            ) : null}
          </div>
        </div>

        <div className="min-h-0 overflow-hidden rounded-xl border border-white/10 bg-black/30">
          <div className="border-b border-white/10 px-3 py-2 text-xs text-white/60">
            {selectedFilePath || "Select a file to preview"}
          </div>
          <pre className="h-full min-h-0 overflow-auto p-3 text-[12px] leading-relaxed text-white/80">
            {selectedFilePath
              ? fileContent || (loading ? "Loading..." : "No text content / unavailable.")
              : "Select a file from the list."}
          </pre>
        </div>
      </div>
    </section>
  );
}
