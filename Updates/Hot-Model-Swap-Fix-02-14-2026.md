# Hot Model Swapping Fix - February 14, 2026

## Problem

When switching providers or models in the UI:
- ✅ Model selection API was called successfully
- ✅ Backend config was updated
- ❌ **But the websocket session kept using the old model**

**Evidence from logs**:
```
INFO: Active model switched: qwen3-next-instruct -> claude-opus-4-6
...
LLM REQUEST PAYLOAD:
"model": "qwen3-next-instruct"  ← Still using old model!
```

## Root Cause

1. Websocket session creates an `llm_client` instance at startup
2. When user switches models, the API updates `aether.nvidia.config.model`
3. **But the session's runtime still has the old `llm_client` instance**
4. Subsequent requests use the cached client with the old model

## Solution: Hot Model Swapping

Added a new websocket message type `"update_model"` that recreates the LLM client without reconnecting.

### Backend Changes

**File**: `aether/agent_websocket.py`

1. **Added message handler** (line 290):
```python
elif msg_type == "update_model":
    # Hot-swap the model without reconnecting
    await self._handle_model_update(websocket, runtime, session_id)
```

2. **Added `_handle_model_update` method** (lines 390-444):
```python
async def _handle_model_update(self, websocket, runtime, session_id):
    """Update the LLM client when provider/model changes."""
    # Get current provider config from provider_router
    llm_config = self.provider_router.get_llm_config()
    provider_config = self.provider_router.get_current_provider_config()
    provider_name = provider_config.get("name", "unknown")
    model = llm_config.get("default_model")

    # Create new LLM client
    new_llm_client = NVIDIAKit(
        api_key=llm_config.get("api_key") or "",
        base_url=llm_config.get("base_url"),
        model=model,
        provider=provider_name
    )

    # Update runtime's LLM client
    runtime.llm = new_llm_client

    # Notify client
    await self._send_event(websocket, {
        "event_type": "model_updated",
        "payload": {"provider": provider_name, "model": model}
    })
```

### Frontend Changes

**File**: `ui/client/src/hooks/useAgentRuntime.ts`

Added `updateModel` method (lines 387-397):
```typescript
const updateModel = useCallback(() => {
  if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

  wsRef.current.send(
    JSON.stringify({
      type: "update_model",
    })
  );
}, []);
```

Exported in return (line 418):
```typescript
return {
  // ... other methods
  updateModel,
};
```

**File**: `ui/client/src/components/AetherPanelV2.tsx`

1. **Destructured `updateModel`** (line 120):
```typescript
const { ..., updateModel } = useAgentRuntime(sessionId);
```

2. **Call after model selection** (lines 129-132):
```typescript
const selectBackendModel = async (modelId: string, silent = false) => {
  const data = await apiFetch("/api/models/select", {...});

  // Hot-swap the model in the active websocket session
  if (updateModel) {
    updateModel();
  }

  // ... toast notifications
}
```

## How It Works

1. User selects new provider/model in UI
2. Frontend calls `/api/models/select` → backend config updated
3. Frontend sends `{"type": "update_model"}` websocket message
4. Backend receives message
5. Backend gets current provider/model from `provider_router`
6. Backend creates new `NVIDIAKit` instance with new provider/model
7. Backend updates `runtime.llm = new_llm_client`
8. Backend sends `"model_updated"` event to frontend
9. **Next LLM request uses new model** ✅

## Benefits

✅ **No reconnection required** - Session stays alive
✅ **No message history loss** - Context preserved
✅ **Instant switching** - Sub-second model swap
✅ **Works for all providers** - Anthropic, OpenRouter, Nvidia, etc.
✅ **Graceful error handling** - Sends error event if swap fails

## Testing

### Via UI:
1. Start a conversation with any model
2. Switch provider (e.g., litellm → anthropic)
3. Switch model (e.g., claude-opus-4-6)
4. Send another message
5. **Check logs**: Should show new model in LLM REQUEST PAYLOAD

### Via Logs:
Look for these messages:
```
INFO: Hot-swapping to provider: anthropic, model: claude-opus-4-6
INFO: Session abc123 model updated to: anthropic/claude-opus-4-6
```

Then in LLM request:
```
"model": "claude-opus-4-6"  ← Correct!
```

### Via Browser Console:
Listen for the `model_updated` event:
```javascript
// In browser DevTools console
// (WebSocket events are logged automatically)
```

## Edge Cases Handled

1. **Provider router unavailable**: Logs warning, doesn't crash
2. **Invalid provider/model**: Sends error event to client
3. **Websocket closed**: Method returns early (no-op)
4. **updateModel called when not connected**: Returns early (no-op)

## Files Modified

1. **Backend**:
   - `aether/agent_websocket.py` - Added update_model handler

2. **Frontend**:
   - `ui/client/src/hooks/useAgentRuntime.ts` - Added updateModel method
   - `ui/client/src/components/AetherPanelV2.tsx` - Call updateModel after selection

## Result

🎉 **Models now hot-swap instantly without reconnecting!**

You can switch from Qwen to Claude Opus mid-conversation and see the difference immediately.

---

## Example Session Flow

```
User: "What tools are available?"
[Using qwen3-next-instruct]
Agent: [Lists tools...]

User: [Switches to Claude Opus 4.6]
[Backend] Hot-swapping to provider: anthropic, model: claude-opus-4-6
[Backend] Session updated to: anthropic/claude-opus-4-6
[Frontend] Received model_updated event

User: "Analyze the codebase structure"
[Using claude-opus-4-6]
Agent: [More sophisticated analysis with Claude Opus...]
```

No reconnection. No context loss. Just a better model. ✨
