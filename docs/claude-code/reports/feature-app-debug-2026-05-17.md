# Relatório de Feature — APP_DEBUG

**Data**: 2026-05-17
**Tipo**: Nova funcionalidade
**Variável de ambiente**: `APP_DEBUG` (boolean, default `false`)

---

## Funcionamento

Quando `APP_DEBUG=true` no `.env` ou `os.environ`, a aplicação cria uma pasta de debug em `~/.deepseek-tui/sessions/debug_YYYYMMDD_HHMMSS/` com dois ficheiros:

| Ficheiro | Conteúdo |
|---|---|
| `session.log` | Registo textual de toda a atividade: input do utilizador, output exibido, erros, tool calls |
| `prompts.json` | Array JSON com todos os prompts enviados à API, `reasoning_content` gerado, e resultados das tools |

### Formato do `session.log`

```
[2026-05-17T14:30:01.123456] [USER] Faz uma analise do projeto
[2026-05-17T14:30:01.234567] [SYSTEM] a pensar...
[2026-05-17T14:30:02.345678] [OUTPUT] Aqui esta a analise...
[2026-05-17T14:30:05.456789] [TOOL] name=list_dir args={"path":"."} result=Conteudo de '.' ...
[2026-05-17T14:30:06.567890] [ERROR] Traceback (most recent call last): ...
```

### Formato do `prompts.json`

```json
[
  {
    "timestamp": "2026-05-17T14:30:01.234567",
    "messages": [
      {"role": "system", "content": "Voce e o assistente..."},
      {"role": "user", "content": "Faz uma analise do projeto"}
    ],
    "tools": [{"type": "function", "function": {"name": "list_dir", ...}}]
  },
  {
    "timestamp": "2026-05-17T14:30:02.345678",
    "reasoning_content": "O utilizador pediu uma analise do projeto..."
  },
  {
    "timestamp": "2026-05-17T14:30:05.456789",
    "tool_name": "list_dir",
    "tool_result": "Conteudo de '.' (max_depth=2, pattern='*'):\n  [F] README.md..."
  }
]
```

---

## Arquitetura

### `config/debug_logger.py` — Módulo central

Singleton `DebugLogger` com dois mecanismos de log:

**Log textual** (`session.log`):
- `log_user_input(text)` — input do utilizador
- `log_output(text)` — chunks de output exibidos na TUI
- `log_error(text)` — exceções e mensagens de erro
- `log_system(text)` — mensagens do sistema
- `log_tool_call(tool_name, args, result)` — execução de ferramentas

**Log JSON** (`prompts.json`):
- `log_prompt(messages, tools)` — array completo de mensagens + tools enviados ao provider
- `log_reasoning(content)` — `reasoning_content` dos chunks de streaming
- `log_tool_result(tool_name, result)` — resultado da execução de cada tool

O singleton é acedido via `DebugLogger.get_instance()` que retorna `None` quando `app_debug=False`, permitindo código de log sem verificações condicionais explícitas.

### `config/settings.py` — Nova variável

- Campo `app_debug: bool = False` na dataclass `Settings`
- Lido do `.env` ou `os.environ["APP_DEBUG"]`
- Função `_to_bool()` converte strings `"true"`, `"1"`, `"yes"`, `"on"` para `True`
- `load_settings()` lê `APP_DEBUG` e aplica `_to_bool()`

### Pontos de integração

| Local | O que regista |
|---|---|
| `agent/loop.py:chat_stream()` | User input, prompts enviados, reasoning_content, tool calls e resultados |
| `tui/app.py:on_input_submitted()` | Output chunks exibidos, erros de exceção |

---

## Como ativar

Adicionar ao ficheiro `~/.deepseek-tui/.env`:

```dotenv
APP_DEBUG=true
```

Ou via variável de ambiente antes de executar:

```bash
set APP_DEBUG=true
pipenv run pydeepseek
```

Os logs aparecem em `~/.deepseek-tui/sessions/debug_YYYYMMDD_HHMMSS/`.

---

## Ficheiros Alterados

| Ficheiro | Alteração |
|---|---|
| `src/pydeepseek_tui/config/debug_logger.py` | **Novo** — singleton DebugLogger com log textual e JSON |
| `src/pydeepseek_tui/config/settings.py` | Adicionado campo `app_debug`, função `_to_bool()`, leitura da env var |
| `src/pydeepseek_tui/agent/loop.py` | Integração: log de user input, prompts, reasoning, tool calls |
| `src/pydeepseek_tui/tui/app.py` | Integração: log de output chunks e erros |

## Verificação

```
$ pipenv run pytest -v
============================= 53 passed in 5.74s ==============================
```
