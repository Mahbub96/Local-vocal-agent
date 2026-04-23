# Step 3 - Database Design

## 1. SQLite Tables

### Table: `sessions`

- Purpose:
  - stores each conversation session
  - groups messages under one persistent thread

#### Schema

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    user_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at DATETIME,
    is_active INTEGER NOT NULL DEFAULT 1
);
```

#### Notes

- `id` should be a UUID string
- `title` can be auto-generated from the first user message
- `last_message_at` supports fast recent-session lookup

### Table: `messages`

- Purpose:
  - stores every user, assistant, system, and tool message
  - acts as the authoritative conversation log

#### Schema

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    sequence_number INTEGER NOT NULL,
    parent_message_id TEXT,
    tool_name TEXT,
    tool_input TEXT,
    tool_output TEXT,
    token_count INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_message_id) REFERENCES messages(id) ON DELETE SET NULL
);
```

#### Role values

- `user`
- `assistant`
- `system`
- `tool`

#### Content type values

- `text`
- `audio_transcript`
- `tool_result`

#### Notes

- `sequence_number` preserves strict order within a session
- `tool_name`, `tool_input`, `tool_output` support traceability
- `parent_message_id` helps connect tool outputs or follow-up responses

### Table: `metadata`

- Purpose:
  - stores extensible structured attributes without changing the main schema often
  - can attach metadata to either session or message

#### Schema

```sql
CREATE TABLE metadata (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    message_id TEXT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'text',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);
```

#### Examples

- `key = 'intent'`, `value = 'real_time_query'`
- `key = 'source'`, `value = 'google_news_rss'`
- `key = 'embedding_status'`, `value = 'completed'`
- `key = 'audio_path'`, `value = '/tmp/response_123.wav'`

#### Rule

- At least one of `session_id` or `message_id` should be present.
- The application layer should enforce this.

## 2. Relationships

```text
sessions
   |
   | 1-to-many
   v
messages
   |
   | 1-to-many
   v
metadata
```

### Relationship Summary

- One `session` has many `messages`
- One `message` belongs to one `session`
- One `message` can have many `metadata` records
- One `session` can also have many `metadata` records

## 3. Indexing Strategy

### For `sessions`

```sql
CREATE INDEX idx_sessions_updated_at ON sessions(updated_at DESC);
CREATE INDEX idx_sessions_last_message_at ON sessions(last_message_at DESC);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
```

#### Why

- Fast recent-session listing
- Fast session filtering by user

### For `messages`

```sql
CREATE INDEX idx_messages_session_id_seq
ON messages(session_id, sequence_number);

CREATE INDEX idx_messages_created_at
ON messages(created_at DESC);

CREATE INDEX idx_messages_role
ON messages(role);

CREATE INDEX idx_messages_parent_message_id
ON messages(parent_message_id);
```

#### Why

- `session_id + sequence_number` is the main ordered conversation retrieval path
- `created_at` helps recent history queries
- `role` helps filtering user or assistant messages
- `parent_message_id` helps tool-chain reconstruction

### For `metadata`

```sql
CREATE INDEX idx_metadata_session_id ON metadata(session_id);
CREATE INDEX idx_metadata_message_id ON metadata(message_id);
CREATE INDEX idx_metadata_key ON metadata(key);
CREATE INDEX idx_metadata_key_value ON metadata(key, value);
```

#### Why

- Fast retrieval of metadata by object id
- Efficient filtering for operational fields like `embedding_status`, `intent`, and `source`

## 4. Query Strategy

### Recent conversation load

```sql
SELECT *
FROM messages
WHERE session_id = ?
ORDER BY sequence_number DESC
LIMIT ?;
```

### Fetch semantic search results by ids

```sql
SELECT *
FROM messages
WHERE id IN (?, ?, ?, ?);
```

### Fetch full chronological context for selected session

```sql
SELECT *
FROM messages
WHERE session_id = ?
ORDER BY sequence_number ASC;
```

### Performance Rule

- Never scan all messages
- Always query by indexed columns:
  - `session_id`
  - `sequence_number`
  - `id`
  - `created_at`
  - metadata keys where needed

## 5. ChromaDB Design

### Collection Structure

- Primary collection:
  - `conversation_memory`

### Document Unit

- One Chroma document per message
- Later extension:
  - one document per summarized conversation chunk

### Why per-message first

- Fine-grained semantic recall
- Simpler traceability back to SQLite
- Easy mapping from vector result to full structured record

## 6. Embedding Strategy

### Input to embedding

- Mainly user messages
- Optionally assistant messages
- Recommended production approach:
  - embed both user and assistant messages
  - mark role in metadata

### Embedded text format

```text
Session: {session_id}
Role: {role}
Message: {content}
```

### Reason

- Gives semantic model enough context
- Improves retrieval quality compared to raw message text alone

### Insertion flow

```text
Message saved to SQLite
   |
   v
Background embedding job
   |
   v
Generate embedding
   |
   v
Store in Chroma with message_id reference
```

## 7. Chroma Metadata Fields

Each vector entry should include:

- `message_id`
- `session_id`
- `role`
- `created_at`
- `sequence_number`
- `content_type`
- `source`
- `has_tool_usage`
- `tool_name`

### Example

```json
{
  "message_id": "msg_123",
  "session_id": "sess_001",
  "role": "user",
  "created_at": "2026-04-22T10:30:00Z",
  "sequence_number": 12,
  "content_type": "text",
  "source": "chat",
  "has_tool_usage": false,
  "tool_name": null
}
```

## 8. Chroma Record Shape

### Document

```text
"I prefer concise answers and I asked earlier about local Whisper setup."
```

### ID

```text
msg_123
```

### Metadata

```json
{
  "message_id": "msg_123",
  "session_id": "sess_001",
  "role": "user",
  "sequence_number": 12,
  "created_at": "2026-04-22T10:30:00Z"
}
```

## 9. Retrieval Flow with SQLite + Chroma

```text
User Query
   |
   v
Generate query embedding
   |
   v
Search ChromaDB top-k
   |
   v
Get message_ids
   |
   v
Fetch full rows from SQLite
   |
   v
Sort, compress, deduplicate
   |
   v
Inject into LLM context
```

### Why this split is important

- Chroma is optimized for similarity search
- SQLite is optimized for authoritative storage and relational access
- Combining them avoids vector-store-only limitations

## 10. Recommended Retrieval Constraints

- `top_k`: 3 to 8 results per query
- Max retrieved sessions: 2 to 3
- Max injected memory characters or tokens:
  - enforce a strict cap before LLM call
- Prefer newest result when semantic scores are close
- Deduplicate adjacent messages from the same session

## 11. Summary of Responsibilities

### SQLite

- Permanent structured source of truth
- Session and message ordering
- Metadata and auditability
- Exact lookup by ids

### ChromaDB

- Semantic similarity retrieval
- Fast top-k vector search
- Lightweight metadata filtering
