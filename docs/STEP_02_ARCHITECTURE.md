# Step 2 - Architecture Design

## 1. Data Flow

- User sends text or audio input.
- If the input is audio:
  - Audio -> STT module (Whisper) -> transcribed text
- Input text enters the assistant pipeline.
- System loads recent short-term memory.
- System performs semantic retrieval on long-term memory.
- Decision engine checks whether the query needs:
  - memory
  - database lookup
  - internet search
- Assistant orchestration decides internet usage using deterministic routing rules.
- Ollama Qwen model generates the response.
- Response is stored in SQLite and embedded into ChromaDB.
- If voice output is requested:
  - Response text -> TTS module -> audio output
- API returns text or audio response.

### ASCII Flow

```text
User Input
   |
   v
Text -----------+
                |
Audio -> Whisper STT
                |
                v
         Normalized Text
                |
                v
       Decision Engine
   +--------+--------+--------+
   |        |        |        |
   v        v        v        v
Memory   SQLite   Chroma   Internet Search
Lookup   Lookup   Search   (Google RSS / DuckDuckGo fallback)
   \        |        |        /
    \       |        |       /
     +------> Assistant Orchestrator
                |
                v
         Ollama Qwen
                |
                v
      Response Persistence Layer
      - SQLite store
      - Chroma embeddings
                |
                v
        Text Response / TTS Audio
```

## 2. Memory Flow: SQLite vs ChromaDB Responsibilities

- `SQLite` is the source of truth for structured conversation history.
- `ChromaDB` is the semantic retrieval layer for meaning-based recall.
- `Short-term memory` holds the most recent exchanges for fast context injection.
- `Long-term memory` is persisted permanently across sessions.

### Responsibilities

#### SQLite

- Store sessions
- Store messages in chronological order
- Store metadata such as timestamps, role, tool usage, source type
- Support exact filtering by session, date, role, and message id
- Fetch full messages once Chroma returns matching ids

#### ChromaDB

- Store embeddings of user and assistant messages
- Perform top-k semantic similarity search
- Return message ids and metadata references
- Avoid scanning all prior conversations

### Memory Retrieval Flow

```text
New User Query
   |
   v
Embed Query
   |
   v
Search ChromaDB (top-k similar messages)
   |
   v
Get matching message/session IDs
   |
   v
Fetch full records from SQLite
   |
   v
Compress / limit context
   |
   v
Inject into LLM prompt
```

## 3. Decision Engine Logic

### When to use memory

- Use memory for:
  - follow-up questions
  - personal preferences
  - previous tasks
  - prior conversation references
  - contextual continuity
- Trigger memory retrieval when:
  - query contains references like "earlier", "before", "last time", "remember"
  - query is ambiguous and likely depends on prior context
  - system wants relevant historical context by default

### When to search internet

- Use internet search only when the query is real-time or externally changing.
- Examples:
  - weather
  - live news
  - current prices
  - recent events
  - latest releases
- If query is not real-time:
  - skip internet
  - use memory + LLM only

### Decision Logic

```text
If input is audio:
  transcribe first

If query is real-time / current-events dependent:
  use internet search tool (default provider: Google News RSS)

Else:
  use memory retrieval
  use SQLite + Chroma context

Then:
  send assembled context to assistant orchestrator + Qwen
```

### Suggested Rule Order

- Step 1: detect modality (`text` or `audio`)
- Step 2: classify intent (`real-time` vs `non-real-time`)
- Step 3: retrieve short-term context
- Step 4: retrieve semantic long-term memory if useful
- Step 5: execute tool path
- Step 6: generate response
- Step 7: persist everything

## 4. Assistant Orchestration Structure

- Assistant orchestration handles deterministic tool routing.
- Main components:
  - LLM wrapper for Ollama Qwen
  - Search client (Google News RSS default, DuckDuckGo fallback)
  - Prompt template
  - Decision routing logic
  - Memory/context assembler

### Agent Tools

- `memory_search_tool`
  - queries ChromaDB
  - returns relevant past conversation snippets
- `internet_search_tool`
  - uses configured web source for real-time information
- optional internal utility tools
  - session resolver
  - metadata fetcher

### Agent Structure

```text
User Query
   |
   v
Prompt Builder
   |
   +-- system instructions
   +-- short-term memory
   +-- retrieved long-term memory
   +-- tool descriptions
   |
   v
Assistant Orchestrator
   |
   +-- Tool: memory_search_tool
   +-- Tool: internet_search_tool
   |
   v
Ollama Qwen
   |
   v
Final Response
```

### Practical Design

- Use a central `AssistantOrchestrator`
- Use deterministic orchestration with explicit tool routing
- Keep memory retrieval service separate from the agent
- Keep tool wrappers thin and focused
- Keep prompt assembly outside route handlers

## 5. TTS/STT Integration

### STT Integration

- `/voice-chat` receives audio file
- STT service runs Whisper locally
- Whisper returns transcribed text
- Transcribed text enters the same assistant pipeline as normal text chat

### TTS Integration

- After text response is generated
- TTS service converts text -> waveform/audio file
- API returns:
  - text
  - optional audio path or streamed audio

### Voice Pipeline

```text
Audio Input
   |
   v
Whisper STT
   |
   v
Text Query
   |
   v
Assistant Pipeline
   |
   v
Text Response
   |
   v
Coqui TTS
   |
   v
Audio Output
```

### Integration Notes

- STT should run before agent invocation
- TTS should run after response generation
- TTS can be backgrounded for performance when needed
- Voice and text routes should share the same core orchestration service
- Only input/output modality should differ; reasoning path should remain the same

## 6. Search Provider Behavior

- Config key: `SEARCH_PROVIDER`
  - `google` (default)
  - `duckduckgo`
- Provider behavior:
  - Prothom Alo-related queries use Prothom Alo RSS source.
  - Generic realtime queries use Google News RSS in default mode.
  - If provider returns no results, fallback source is used.

## 7. High-Level Service Layout

```text
API Layer
  -> Chat Service
  -> Voice Service

Voice Service
  -> Whisper STT
  -> Chat Service
  -> Coqui TTS

Chat Service
  -> Decision Engine
  -> Memory Service
  -> Assistant Orchestrator
  -> Ollama Wrapper
  -> Persistence Layer
```
