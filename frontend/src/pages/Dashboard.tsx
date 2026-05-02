import { useCallback, useEffect, useMemo, useState } from "react";
import { useLiveSpeechTranscript } from "../hooks/useLiveSpeechTranscript";
import {
  useVoiceCapture,
  type VoiceCaptureMode,
} from "../hooks/useVoiceCapture";
import { TopBar } from "../components/layout/TopBar";
import { StatusBar } from "../components/layout/StatusBar";
import { MobileContextTabs } from "../components/layout/MobileContextTabs";
import { Sidebar } from "../components/Sidebar";
import { ChatPanel } from "../components/ChatPanel";
import { MemoryPanel } from "../components/MemoryPanel";
import { ThinkingPanel } from "../components/ThinkingPanel";
import { ToolsPanel } from "../components/ToolsPanel";
import { VoicePanel } from "../components/VoicePanel";
import { useAuroraDashboard } from "../hooks/useAuroraDashboard";
import { modelDisplayName } from "../config";

/**
 * Aurora AI Assistant — full dashboard layout (voice, chat, context rails).
 * Uses live API data from `useAuroraDashboard`.
 *
 * Responsive: below `xl`, navigation is an off-canvas drawer. Below `lg`, context
 * panels (thinking / memory / tools) use tabs to stay within the viewport.
 */
export function Dashboard() {
  const [navOpen, setNavOpen] = useState(false);
  const [captureMode, setCaptureMode] = useState<VoiceCaptureMode>("push");

  const {
    messages,
    input,
    setInput,
    metrics,
    thinking,
    activities,
    profile,
    voiceStatus,
    systemStatus,
    fileEntriesCount,
    totalMessageCount,
    totalTokens,
    loading,
    error,
    sendMessage,
    activeSessionTitle,
    dayLabel,
    lastAssistantText,
    streamingAssistantText,
    ttsRevealText,
    userInitial,
    submitFeedback,
    saveProfile,
    allSystemsOk,
    sendVoiceBlob,
    stopVoicePlayback,
  } = useAuroraDashboard();

  const voiceLanguageLabel = profile?.language?.trim() || "Default";

  const {
    isHot,
    micLevel,
    error: captureError,
    togglePush,
    interrupt,
    discardPush,
  } = useVoiceCapture({
    mode: captureMode,
    busy: loading,
    onUtterance: sendVoiceBlob,
    onBargeIn: stopVoicePlayback,
  });

  const { displayText: liveUserText } = useLiveSpeechTranscript(
    isHot,
    voiceLanguageLabel,
  );

  const setCaptureModeSafe = useCallback(
    (next: VoiceCaptureMode) => {
      if (next === "always" && captureMode === "push" && isHot) {
        void discardPush();
      }
      setCaptureMode(next);
    },
    [captureMode, isHot, discardPush],
  );

  const handleMicOrHandsFree = useCallback(() => {
    if (loading) return;
    if (captureMode === "always") {
      setCaptureMode("push");
      return;
    }
    void togglePush();
  }, [loading, captureMode, togglePush]);

  const handleVoiceInterrupt = useCallback(() => {
    interrupt();
  }, [interrupt]);

  const combinedError = useMemo(
    () => [error, captureError].filter(Boolean).join(" · ") || "",
    [error, captureError],
  );

  const voiceLiveCaption = streamingAssistantText || ttsRevealText;

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  return (
    <div className="flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden bg-[#0b0d17] bg-[radial-gradient(ellipse_120%_85%_at_50%_-25%,rgba(0,210,255,0.11),transparent_55%),radial-gradient(ellipse_70%_50%_at_100%_30%,rgba(157,80,187,0.07),transparent_50%)] text-aurora-fg">
      <TopBar userInitial={userInitial} onMenuClick={() => setNavOpen(true)} />

      {navOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/60 xl:hidden"
          aria-label="Close navigation menu"
          onClick={() => setNavOpen(false)}
        />
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
        <div
          className={`aurora-drawer fixed inset-y-0 left-0 z-50 flex min-h-0 w-[min(280px,88vw)] max-w-[280px] shrink-0 transition-transform duration-300 ease-out xl:relative xl:z-0 xl:max-w-none xl:translate-x-0 xl:shadow-none ${
            navOpen ? "translate-x-0" : "-translate-x-full xl:translate-x-0"
          }`}
        >
          <Sidebar
            metrics={metrics}
            fileEntryCount={fileEntriesCount}
            onRequestClose={() => setNavOpen(false)}
            className="h-full min-h-0 border-0"
          />
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-2 sm:gap-4 sm:p-3 md:p-4 lg:flex-row lg:gap-4">
            <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-hidden sm:gap-4 lg:min-w-0">
              <div className="shrink-0">
                <VoicePanel
                  voiceStatus={voiceStatus}
                  languageLabel={voiceLanguageLabel}
                  lastAssistantSnippet={lastAssistantText}
                  liveAssistantOutput={voiceLiveCaption}
                  captureMode={captureMode}
                  onCaptureModeChange={setCaptureModeSafe}
                  isListening={isHot}
                  liveUserText={liveUserText}
                  micLevelLocal={micLevel}
                  voiceBusy={loading}
                  onMicPrimary={handleMicOrHandsFree}
                  onVoiceInterrupt={handleVoiceInterrupt}
                  onLanguageChange={
                    profile
                      ? (language) => {
                          void saveProfile({ ...profile, language });
                        }
                      : undefined
                  }
                />
              </div>
              <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                <ChatPanel
                  title={activeSessionTitle}
                  sessionDayTime={dayLabel}
                  messages={messages}
                  input={input}
                  loading={loading}
                  onInputChange={setInput}
                  onSubmit={sendMessage}
                  onFeedback={submitFeedback}
                  streamingAssistantText={streamingAssistantText}
                  voiceCaptureMode={captureMode}
                  isVoiceHot={isHot}
                  onVoicePrimary={handleMicOrHandsFree}
                />
              </div>
              {combinedError ? (
                <p className="shrink-0 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
                  {combinedError}
                </p>
              ) : null}
            </main>

            <div className="flex min-h-[200px] max-h-[min(44vh,420px)] min-w-0 shrink-0 flex-col lg:hidden">
              <MobileContextTabs
                thinking={thinking}
                profile={profile}
                onSaveProfile={saveProfile}
                activities={activities}
              />
            </div>

            <aside
              className="hidden min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto overflow-x-hidden lg:flex lg:w-[min(300px,32vw)] lg:max-w-[320px] lg:shrink-0 xl:w-aurora-context"
              aria-label="Context panels"
            >
              <ThinkingPanel thinking={thinking} />
              <MemoryPanel profile={profile} onSave={saveProfile} />
              <ToolsPanel activities={activities} />
            </aside>
          </div>

          <StatusBar
            modelName={systemStatus?.model_name || modelDisplayName}
            uptimeSeconds={systemStatus?.uptime_seconds ?? null}
            totalResponses={totalMessageCount}
            totalTokens={totalTokens}
            allSystemsOk={allSystemsOk}
          />
        </div>
      </div>
    </div>
  );
}
