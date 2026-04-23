import { SideRail } from "./components/layout/SideRail";
import { StatusBar } from "./components/layout/StatusBar";
import { TopBar } from "./components/layout/TopBar";
import { ActivityPanel } from "./components/panels/ActivityPanel";
import { ChatPanel } from "./components/panels/ChatPanel";
import { MemoryPanel } from "./components/panels/MemoryPanel";
import { ThinkingPanel } from "./components/panels/ThinkingPanel";
import { VoicePanel } from "./components/panels/VoicePanel";
import { useAuroraDashboard } from "./hooks/useAuroraDashboard";
import { modelDisplayName } from "./config";

function App() {
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
    userInitial,
    submitFeedback,
    saveProfile,
    allSystemsOk,
  } = useAuroraDashboard();

  const voiceLanguageLabel = profile?.language?.trim() || "Default";

  return (
    <div className="aurora-page">
      <SideRail metrics={metrics} brandInitial="A" fileEntryCount={fileEntriesCount} />
      <div className="main-shell">
        <TopBar userInitial={userInitial} />
        <div className="content-grid">
          <div className="content-center">
            <VoicePanel
              voiceStatus={voiceStatus}
              languageLabel={voiceLanguageLabel}
              lastAssistantSnippet={lastAssistantText}
              onLanguageChange={
                profile
                  ? (language) => {
                      void saveProfile({ ...profile, language });
                    }
                  : undefined
              }
            />
            <ChatPanel
              title={activeSessionTitle}
              sessionDayTime={dayLabel}
              messages={messages}
              input={input}
              loading={loading}
              onInputChange={setInput}
              onSubmit={sendMessage}
              onFeedback={submitFeedback}
            />
          </div>
          <aside className="content-rail">
            <ThinkingPanel thinking={thinking} />
            <MemoryPanel profile={profile} onSave={saveProfile} />
            <ActivityPanel activities={activities} />
          </aside>
        </div>
        {error ? <p className="error app-error">{error}</p> : null}
        <StatusBar
          modelName={systemStatus?.model_name || modelDisplayName}
          uptimeSeconds={systemStatus?.uptime_seconds ?? null}
          totalResponses={totalMessageCount}
          totalTokens={totalTokens}
          allSystemsOk={allSystemsOk}
        />
      </div>
    </div>
  );
}

export default App;
