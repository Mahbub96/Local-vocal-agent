/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLiveSpeechTranscript } from "../hooks/useLiveSpeechTranscript";
import {
  useVoiceCapture,
  type VoiceCaptureMode,
} from "../hooks/useVoiceCapture";
import { TopBar } from "../components/layout/TopBar";
import { StatusBar } from "../components/layout/StatusBar";
import { MobileContextTabs } from "../components/layout/MobileContextTabs";
import type { MobileContextTabId } from "../components/layout/MobileContextTabs";
import { Sidebar } from "../components/Sidebar";
import { ChatPanel } from "../components/ChatPanel";
import { MemoryPanel } from "../components/MemoryPanel";
import { ThinkingPanel } from "../components/ThinkingPanel";
import { ToolsPanel } from "../components/ToolsPanel";
import { ToolsWorkspace } from "../components/ToolsWorkspace";
import { VoicePanel } from "../components/VoicePanel";
import { SearchWorkspace } from "../components/SearchWorkspace";
import { SettingsWorkspace } from "../components/SettingsWorkspace";
import { FilesWorkspace } from "../components/FilesWorkspace";
import { useAuroraDashboard } from "../hooks/useAuroraDashboard";
import { modelDisplayName } from "../config";
import type { NavItem } from "../components/layout/navConfig";

const FORCE_STOP_VOICE_RE =
  /\b(stop|stop speaking|stop now|be quiet|quiet|that's enough|thats enough|enough)\b|থামো|থামুন|বন্ধ করো|চুপ/i;

/**
 * Aurora AI Assistant — full dashboard layout (voice, chat, context rails).
 * Uses live API data from `useAuroraDashboard`.
 *
 * Responsive: below `xl`, navigation is an off-canvas drawer. Below `lg`, context
 * panels (thinking / memory / tools) use tabs to stay within the viewport.
 */
export function Dashboard() {
  const [navOpen, setNavOpen] = useState(false);
  const [activeNav, setActiveNav] = useState<NavItem>("Home");
  const [mobileContextTab, setMobileContextTab] = useState<MobileContextTabId>("think");
  const voiceSectionRef = useRef<HTMLDivElement | null>(null);
  const chatSectionRef = useRef<HTMLDivElement | null>(null);
  const mobileContextRef = useRef<HTMLDivElement | null>(null);
  const memorySectionRef = useRef<HTMLDivElement | null>(null);
  const toolsSectionRef = useRef<HTMLDivElement | null>(null);
  /** Default hands-free: voice auto-sends after speech pause. */
  const [captureMode, setCaptureMode] = useState<VoiceCaptureMode>("always");

  const {
    activeSessionId,
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
    lastAssistantText,
    streamingAssistantText,
    ttsRevealText,
    userInitial,
    submitFeedback,
    saveProfile,
    allSystemsOk,
    sendVoiceBlob,
    stopVoicePlayback,
    voiceGateHint,
    voiceUploadBusy,
    ttsAudioPlaying,
  } = useAuroraDashboard();

  const isAssistantSpeaking = useMemo(
    () => ttsAudioPlaying || (voiceStatus?.state ?? "").toLowerCase() === "speaking",
    [ttsAudioPlaying, voiceStatus?.state],
  );

  /** Silent mode + hands-free would flood skipped clips with no feedback — force push-to-talk. */
  useEffect(() => {
    if (profile?.voice_listen_paused && captureMode === "always") {
      setCaptureMode("push");
    }
  }, [profile?.voice_listen_paused, captureMode]);

  const voiceLanguageLabel = profile?.language?.trim() || "Default";

  const {
    isHot,
    isListeningUi,
    utteranceSeq,
    micLevel,
    error: captureError,
    togglePush,
    interrupt,
    discardPush,
  } = useVoiceCapture({
    mode: captureMode,
    busy: voiceUploadBusy,
    // While assistant is speaking, keep playback uninterrupted by default.
    // Force-stop is handled via explicit stop phrase detection below.
    onUtterance: async (blob) => {
      if (isAssistantSpeaking) return;
      await sendVoiceBlob(blob, liveUserText);
    },
    onBargeIn: stopVoicePlayback,
    // Keep acoustic barge-in enabled so saying "stop" can interrupt reliably
    // even when live speech transcript misses a word.
    suppressBargeIn: false,
  });

  const { displayText: liveUserText } = useLiveSpeechTranscript(
    isHot,
    voiceLanguageLabel,
    utteranceSeq,
  );
  const forceStopLatchRef = useRef(false);

  const setCaptureModeSafe = useCallback(
    (next: VoiceCaptureMode) => {
      if (next === "always" && profile?.voice_listen_paused) {
        return;
      }
      if (next === "always" && captureMode === "push" && isHot) {
        void discardPush();
      }
      setCaptureMode(next);
    },
    [captureMode, isHot, discardPush, profile?.voice_listen_paused],
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
    if (captureMode === "always") {
      // Explicit stop in hands-free should fully exit always-listen mode.
      stopVoicePlayback();
      setCaptureMode("push");
      return;
    }
    interrupt();
  }, [captureMode, interrupt, stopVoicePlayback]);

  useEffect(() => {
    if (!isAssistantSpeaking) {
      forceStopLatchRef.current = false;
      return;
    }
    const heard = liveUserText.trim();
    if (!heard) return;
    if (!FORCE_STOP_VOICE_RE.test(heard)) return;
    if (forceStopLatchRef.current) return;
    forceStopLatchRef.current = true;
    stopVoicePlayback();
    // A force stop should also end hands-free listening phase.
    setCaptureMode("push");
  }, [isAssistantSpeaking, liveUserText, stopVoicePlayback]);

  const combinedError = useMemo(
    () => [error, captureError].filter(Boolean).join(" · ") || "",
    [error, captureError],
  );

  const voiceLiveCaption = streamingAssistantText || ttsRevealText;
  const chatOnly = activeNav === "Chat";
  const memoryFocused = activeNav === "Memory";
  const settingsFocused = activeNav === "Settings";
  const toolsFocused = activeNav === "Tools";
  const filesFocused = activeNav === "Files";
  const searchFocused = activeNav === "Search";

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  const handleNavSelect = useCallback((item: NavItem) => {
    setActiveNav(item);
    const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
    if (item === "Home") {
      voiceSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (item === "Chat") {
      // Main panel is grid-based (not page-scroll), so switch to chat-focused layout.
      window.setTimeout(() => {
        const el = chatSectionRef.current?.querySelector("textarea");
        if (el instanceof HTMLTextAreaElement) el.focus();
      }, 120);
    } else if (item === "Memory" || item === "Settings") {
      if (isDesktop) memorySectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      else {
        setMobileContextTab("memory");
        mobileContextRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else if (item === "Tools") {
      if (isDesktop) toolsSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      else {
        setMobileContextTab("tools");
        mobileContextRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
    setNavOpen(false);
  }, []);

  return (
    <div className="flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden bg-aurora-canvas bg-[radial-gradient(ellipse_120%_85%_at_50%_-25%,rgba(0,210,255,0.11),transparent_55%),radial-gradient(ellipse_70%_50%_at_100%_30%,rgba(157,80,187,0.07),transparent_50%)] text-aurora-fg">
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
            activeNav={activeNav}
            onNavSelect={handleNavSelect}
            onRequestClose={() => setNavOpen(false)}
            className="h-full min-h-0 border-0"
          />
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-1 sm:gap-3 sm:p-2 md:p-2.5 lg:flex-row lg:gap-3">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-hidden sm:gap-3 lg:min-w-0">
              {settingsFocused ? (
                <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <SettingsWorkspace
                    profile={profile}
                    onSaveProfile={saveProfile}
                    captureMode={captureMode}
                    onCaptureModeChange={setCaptureModeSafe}
                  />
                </main>
              ) : toolsFocused ? (
                <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <ToolsWorkspace
                    activities={activities}
                    voiceStatus={voiceStatus}
                    systemStatus={systemStatus}
                  />
                </main>
              ) : filesFocused ? (
                <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <FilesWorkspace />
                </main>
              ) : searchFocused ? (
                <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <SearchWorkspace
                    activeSessionId={activeSessionId}
                    defaultMode="memory"
                  />
                </main>
              ) : memoryFocused ? (
                <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <div className="mb-2 flex items-center justify-between rounded-xl border border-white/10 bg-white/4 px-3 py-2 text-sm text-white/80 sm:px-4">
                    <span className="font-medium">Memory Workspace</span>
                    <span className="text-xs text-white/50">Review and update saved profile context</span>
                  </div>
                  <div ref={memorySectionRef} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
                    <MemoryPanel profile={profile} onSave={saveProfile} />
                  </div>
                </main>
              ) : (
                <>
                  {/*
                    Grid: voice row capped (scroll inside if needed); chat row min ~220px and grows — keeps composer visible.
                  */}
                  <main
                    className={`grid min-h-0 flex-1 gap-2 overflow-hidden sm:gap-3 ${
                      chatOnly
                        ? "grid-rows-[minmax(0,1fr)]"
                        : "grid-rows-[minmax(0,min(400px,36svh))_minmax(220px,1fr)]"
                    }`}
                  >
                    <div
                      ref={voiceSectionRef}
                      className={`min-h-0 overflow-x-hidden overflow-y-auto overscroll-y-contain ${
                        chatOnly ? "hidden" : ""
                      }`}
                    >
                      <VoicePanel
                        voiceStatus={voiceStatus}
                        languageLabel={voiceLanguageLabel}
                        lastAssistantSnippet={lastAssistantText}
                        liveAssistantOutput={voiceLiveCaption}
                        captureMode={captureMode}
                        onCaptureModeChange={setCaptureModeSafe}
                        gateHint={voiceGateHint}
                        isListening={isListeningUi}
                        voiceSessionHot={isHot}
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
                    <div ref={chatSectionRef} className="flex min-h-0 flex-col overflow-hidden">
                      <ChatPanel
                        title={activeSessionTitle}
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
                        voiceListenPaused={profile?.voice_listen_paused === true}
                        voiceWakeSessionActive={profile?.voice_wake_session_active === true}
                        wakeName={profile?.assistant_wake_name?.trim() || null}
                        onTurnOffVoiceSilentMode={
                          profile
                            ? async () => {
                                await saveProfile({
                                  ...profile,
                                  voice_listen_paused: false,
                                  voice_wake_session_active: false,
                                });
                              }
                            : undefined
                        }
                      />
                    </div>
                  </main>
                  {combinedError ? (
                    <p className="shrink-0 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2 py-1.5 text-xs text-rose-100 sm:text-sm">
                      {combinedError}
                    </p>
                  ) : null}
                </>
              )}
            </div>

            <div ref={mobileContextRef} className="flex min-h-[200px] max-h-[min(44vh,420px)] min-w-0 shrink-0 flex-col lg:hidden">
              <MobileContextTabs
                thinking={thinking}
                profile={profile}
                onSaveProfile={saveProfile}
                activities={activities}
                activeTab={mobileContextTab}
                onTabChange={setMobileContextTab}
              />
            </div>

            {!memoryFocused && !searchFocused && !settingsFocused && !filesFocused ? (
              <aside
                className="hidden min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto overflow-x-hidden lg:flex lg:w-[min(300px,32vw)] lg:max-w-[320px] lg:shrink-0 xl:w-aurora-context"
                aria-label="Context panels"
              >
                {toolsFocused ? (
                  <div ref={toolsSectionRef}>
                    <ToolsPanel activities={activities} />
                  </div>
                ) : (
                  <>
                    <ThinkingPanel thinking={thinking} />
                    <div ref={memorySectionRef}>
                      <MemoryPanel profile={profile} onSave={saveProfile} />
                    </div>
                    <div ref={toolsSectionRef}>
                      <ToolsPanel activities={activities} />
                    </div>
                  </>
                )}
              </aside>
            ) : null}
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
