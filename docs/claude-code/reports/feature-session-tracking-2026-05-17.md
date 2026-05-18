# Feature: Session Activity Tracking

**Date:** 2026-05-17
**Type:** Feature implementation
**Tests:** 73 passed, 0 failed

## Summary

Implemented comprehensive session activity tracking for every pydeepseek-tui execution. Added always-on AI interaction logging with token/cost tracking, UUID-based session folders, a manifest.json registry, refactored debug logging, and a live stats display in the TUI header.

## What was done

### New files created (5)

| File | Purpose |
|------|---------|
| `src/pydeepseek_tui/providers/pricing.py` | Pricing table for all providers/models + `calculate_cost()` function |
| `src/pydeepseek_tui/agent/activity.py` | `SessionActivityLogger` singleton with manifest.json and interactions.json management |
| `src/pydeepseek_tui/tui/widgets/session_info.py` | `SessionInfo` widget showing elapsed time, token count, and cost |
| `tests/test_pricing.py` | 7 tests for pricing calculations and edge cases |
| `tests/test_activity.py` | 8 tests for activity logger singleton, interaction logging, stats accumulation |

### Existing files modified (12)

| File | Changes |
|------|---------|
| `providers/base.py` | Added `UsageInfo` NamedTuple for normalized token usage across providers |
| `providers/deepseek.py` | Added `last_usage` attribute; capture token usage from stream chunk `chunk.usage` including `reasoning_tokens` from `completion_tokens_details` |
| `providers/openai.py` | Added `last_usage` attribute; same usage capture pattern as DeepSeek |
| `providers/anthropic.py` | Added `last_usage` attribute; capture usage after stream ends via `stream.get_final_message()`, map Anthropic `input_tokens`/`output_tokens` to `UsageInfo` |
| `agent/loop.py` | Wire `SessionActivityLogger` into the chat loop; after each `stream()` call capture `provider.last_usage`, calculate cost via `calculate_cost()`, log interaction with token/cost/preview data; accumulate and log reasoning content |
| `agent/session.py` | Full UUID session IDs (36 chars instead of hex[:12]), folder-based storage (`sessions/<uuid>/session.json`), backward compat for legacy flat `.json` files, `shutil.rmtree` for folder deletion |
| `config/debug_logger.py` | Accept `session_id` parameter, write `debug.log` into session folder, removed `log_prompt()`/`log_reasoning()`/`log_tool_result()` (only errors + displayed messages remain), added `init()` classmethod |
| `tui/app.py` | Initialize `SessionActivityLogger` first, then `DebugLogger.init(session_id)`, added `SessionInfo` widget in compose, periodic refresh every 5s, save-on-quit via `action_save_and_quit()` |
| `tui/widgets/__init__.py` | Export `SessionInfo` widget |
| `cli/commands.py` | Updated `sessions` command for folder-based structure, reads `manifest.json` or `session.json` |
| `i18n/locales/pt_BR.json` | Added 6 new keys: `session.label`, `session.tokens`, `session.cost`, `session.interactions`, `session.saved`, `session.no_interactions` |
| `i18n/locales/en_US.json` | Added 6 new keys (English equivalents) |

### Tests updated

| File | Changes |
|------|---------|
| `tests/test_session.py` | Updated `test_save_and_load` for 36-char UUID; added `TestSessionFolderStructure` class with 5 new tests for folders, legacy compat, manifest skipping |
| `tests/test_pricing.py` | NEW: 7 tests covering known models, unknown provider/model, zero tokens, large counts |
| `tests/test_activity.py` | NEW: 8 tests covering singleton, interaction persistence, stats, metadata, truncation |

## Directory structure

```
~/.deepseek-tui/sessions/
    manifest.json              # current session: session_id, session_start, last_interaction, provider, model, mode
    <full-uuid>/
        interactions.json      # always-on: array of AI interaction records with tokens/cost
        session.json           # created on save/quit: full conversation history
        debug.log              # only when APP_DEBUG=true: errors + displayed messages only
```

## Edge cases handled

- **Provider returns no usage**: `last_usage` stays `None`; interaction logging skipped silently
- **Unknown model in price table**: `calculate_cost()` returns 0.0
- **Backward compat**: `list_sessions()` and `load_session()` still handle old flat `.json` files
- **Manifest.json**: skipped by `list_sessions()` to avoid false entries
- **Preview truncation**: prompt and response previews capped at 200 chars in interactions.json
- **Anthropic usage format**: Normalized from `input_tokens`/`output_tokens` to OpenAI-compatible `UsageInfo`
- **DebugLogger not initialized**: Falls back to timestamp-based folder if `init()` wasn't called
