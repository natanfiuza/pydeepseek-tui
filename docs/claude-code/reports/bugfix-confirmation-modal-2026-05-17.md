# Bugfix: Confirmation Modal + Interaction Logging + History Trimming

**Date:** 2026-05-17
**Type:** Bugfix
**Tests:** 73 passed, 0 failed

## Problems fixed

### 1. `prompt_preview` repetitivo no interactions.json
**Antes:** 22 interações todas com `prompt_preview: "O que faz esta minha codebase?"` — o prompt original era usado em todos os rounds de tool call.
**Agora:** Em rounds com tool calls, o preview usa os nomes das ferramentas (ex: `"list_dir, read_file"`). Em rounds sem tool calls, usa o prompt original.

### 2. `response_preview` vazio em rounds de tool call
**Antes:** `response_preview: ""` quando o modelo devolvia apenas tool_calls sem texto.
**Agora:** Quando `response_text` está vazio, usa os nomes das ferramentas como preview.

### 3. Modal de confirmação interativo (substitui texto estático)
**Antes:** `_tui_confirm()` escrevia texto no ChatLog e retornava `False`. O utilizador via a mensagem mas não podia aprovar, causando loops de ferramentas bloqueadas.
**Agora:** Modal `ConfirmScreen(ModalScreen)` com 3 botões:
- **Sim** — aprova esta operação
- **Sim para Todos** — muda para modo YOLO (aprova tudo na sessão)
- **Não** — bloqueia esta operação

### 4. `_trim_history` quebrava pares assistant/tool
**Antes:** Ao truncar o histórico, podia remover uma mensagem `assistant` com `tool_calls` mantendo as `tool` results órfãs, causando erro 400 da API.
**Agora:** Após truncar, remove mensagens `tool` órfãs no início do histórico.

### 5. Respostas textuais não guardadas no histórico
**Antes:** Quando o modelo respondia só com texto (sem tool calls), a resposta não era adicionada ao `conversation_history`.
**Agora:** A resposta é guardada como mensagem `assistant` com `reasoning_content` (quando presente).

## Files changed

| File | Action |
|------|--------|
| `tui/widgets/confirm_screen.py` | CREATE — ModalScreen com 3 botões |
| `tui/widgets/__init__.py` | MODIFY — export ConfirmScreen |
| `tui/app.py` | MODIFY — `_tui_confirm` usa `push_screen` + `asyncio.Future` |
| `agent/loop.py` | MODIFY — 5 fixes (previews, history save, safe trim) |

## Verification

- 73 testes passam
- ruff check: limpo
- black: formatado
