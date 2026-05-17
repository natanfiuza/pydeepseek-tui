# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos

```bash
make dev         # pipenv install --dev
make run         # pipenv run pydeepseek
make test        # pipenv run pytest
make lint        # ruff check + black --check + mypy src
make format      # ruff check --fix + black

# Teste único
pipenv run pytest tests/test_agent.py::test_agent_tool_calling -v

# Atualizar lockfile após mudar dependências
pipenv lock
```

## Arquitetura

### Fluxo de arranque e criptografia

```
cli/commands.py → ensure_api_key() → crypto.decrypt_key(env_var) → os.environ["DEEPSEEK_API_KEY"]
               → ProviderFactory.get_provider() → DeepSeekProvider (lê os.environ diretamente)
               → PyDeepSeekApp() → Agent(provider, registry, mode)
```

A chave da API é guardada encriptada em `~/.deepseek-tui/.env` como `<PREFIX>_API_KEY_ENCRYPTED=<enc>`. A encriptação usa PBKDF2 (100k iterações, SHA-256) com machine-id (usuário + MAC), output Fernet via `config/crypto.py`.

**Importante**: `settings.py` NÃO faz decriptação. Os providers (`DeepSeekProvider`, `OpenAIProvider`, `AnthropicProvider`) leem as chaves diretamente de `os.environ` — NÃO do objeto `settings`. Isto evita race condition de import: `load_settings()` corre ao nível do módulo, mas as env vars só são injetadas depois pelo CLI.

`_save_encrypted_api_key()` em `cli/commands.py` escreve também as variáveis de config padrão (`IA_PROVIDER`, `<PREFIX>_MODEL`, `LANGUAGE`, `DEEPSEEK_BASE_URL`) no `.env`.

### Providers (multi-API)

Todos implementam `BaseAIProvider` (abstrato: `ask()`, `stream()`, `close()`). Cada provider lê as suas env vars diretamente (`os.environ.get("DEEPSEEK_API_KEY")`, etc.):

- `DeepSeekProvider` — `openai.AsyncOpenAI` com `base_url=https://api.deepseek.com`, modelo `deepseek-v4-pro`
- `OpenAIProvider` — `openai.AsyncOpenAI` com base_url padrão, modelo `gpt-4o`
- `AnthropicProvider` — `anthropic.AsyncAnthropic`, converte formato OpenAI ↔ Anthropic (system msg separada, tool calls como content blocks). Adapta streaming Anthropic para formato compatível com o Agent.

`ProviderFactory.get_provider(name)` instancia pelo nome (`deepseek`/`openai`/`anthropic`). Fonte: `--provider` na CLI ou `IA_PROVIDER` no `.env`.

### Agent loop com function calling

`agent/loop.py` — `Agent.chat_stream()`:
1. Envia `conversation_history` + `tools_schema` ao provider via stream
2. Se o provider devolve texto → yield para a TUI
3. Se devolve `tool_calls` → acumula fragmentos (streaming parcial)
4. Verifica `is_destructive` contra o `AgentMode` antes de executar
5. Adiciona tool results ao histórico e recomeça o loop
6. Quando não há mais tool calls → `break`
7. Se `MAX_HISTORY_MESSAGES` (50) for excedido → sliding window preservando system message

### Modos de operação

`AgentMode` (enum em `agent/loop.py`):
- `PLAN` — bloqueia tools com `is_destructive = True`
- `AGENT` — bloqueia tools destrutivas a menos que `on_confirm` callback retorne `True`
- `YOLO` — executa tudo sem confirmação

`BaseTool.is_destructive: bool = False` (em `tools/base.py`). Tools que o definem como `True`: `WriteFileTool`, `ShellTool`, `GitTool`.

### Tools e sandbox

`tools/sandbox.py` — `is_path_allowed(path, allowed_dirs)` usa `os.path.realpath()` + `os.path.commonpath()`. Default: `[os.getcwd()]`.

`registry.py:get_core_registry()` regista 8 tools. O método `get_api_schema()` sanitiza automaticamente os schemas: remove `required` vazio e `default` keywords que causam erro 400 em APIs OpenAI-compatíveis.

### TUI (Textual 8.x)

O projeto usa **Textual 8.2.6**. Nesta versão, `RichLog.write()` NÃO tem parâmetro `markup`.

`tui/widgets/chat.py` — `ChatLog(RichLog)`:
- Usa `rich.text.Text` com `Style(bold=True, color=...)` explícito para mensagens coloridas
- `write_stream()` usa `_safe_markup()`: deteta tags `[bold]` com regex e aplica `Text.from_markup()` se necessário; caso contrário escreve como `Text` puro
- NUNCA usar strings com `[bold green]` markup inline — não funciona no Textual 8.x

`tui/app.py` — Acumula chunks do `chat_stream()` e escreve tudo de uma vez com `log.write_stream(full_response)`. Isto evita que cada chunk vire uma linha separada.

### APP_DEBUG

Variável booleana no `.env` (`APP_DEBUG=true`). Quando ativa, cria `~/.deepseek-tui/sessions/debug_YYYYMMDD_HHMMSS/` com:
- `session.log` — input, output, erros, tool calls (formato `[TIMESTAMP] [LEVEL] mensagem`)
- `prompts.json` — array JSON com prompts enviados, `reasoning_content`, tool results

Singleton `DebugLogger` em `config/debug_logger.py`. Acedido via `DebugLogger.get_instance()` que retorna `None` quando `app_debug=False`.

### Internacionalização

`i18n/translator.py` — Singleton `Translator` com JSON locales em `i18n/locales/{pt_BR,en_US}.json`. Fallback: locale → en_US → key literal. Suporte a `{var}` substitution.

### Sessões e Workspace

`agent/session.py` — `save_session()`, `load_session()`, `list_sessions()`, `delete_session()`. Ficheiros JSON em `~/.deepseek-tui/sessions/`.

`agent/workspace.py` — `Workspace` com `snapshot()` (SHA-256), `undo()`, `undo_all()`. Snapshots em `~/.deepseek-tui/workspace/{session_id}/`.

### Mock pattern nos testes

- `MockProvider` — `stream()` devolve `MockDelta` com `.content` e/ou `.tool_calls`
- `MockToolCall` — simula `.index`, `.id`, `.function.name`, `.function.arguments`
- Providers com tool call DEVEM ter contador (`_call_count`): 1ª chamada → tool call, 2ª → texto. Sem isto o loop é infinito.
- `monkeypatch.setattr("pydeepseek_tui.tools.file_reader.is_path_allowed", ...)` para desativar sandbox
- `monkeypatch.setenv("DEEPSEEK_API_KEY", ...)` é suficiente para o factory test (providers leem `os.environ` diretamente)
- Workspace tests usam `uuid4().hex[:8]` como session_id para evitar contaminação entre runs

## Regras

- Ao finalizar qualquer tarefa, gera um relatório detalhado em `docs/claude-code/reports/`
- NUNCA usar strings com markup `[bold]` no Textual — usar `rich.text.Text` com `Style()` explícito
- Não adicionar `markup=True/False` a chamadas `RichLog.write()` — Textual 8.x não suporta
- Schemas de tools: nunca incluir `"required": []` vazio nem `"default"` nos parâmetros
- Providers leem `os.environ` diretamente, não o objeto `settings`
