# Bugfix: Corrigida a exibicao de mensagens de output no chat

**Branch**: `develop_natan`
**Data**: 2026-05-18

## Problema

Nenhuma das mensagens de output do agente (respostas, execucoes de ferramentas, bloqueios) estava a ser exibida para o utilizador no TUI. Apenas aparecia "Voce: ..." seguido de "a pensar..." e depois nada — ou um erro genérico.

Duas causas raiz:

### Causa 1: `push_screen_wait` crashava fora de worker

O metodo `_tui_confirm()` em `app.py` usava `self.push_screen_wait(screen)` para mostrar o modal de confirmacao. No Textual 8.x, `push_screen_wait` (e `push_screen(wait_for_dismiss=True)`) requerem ser chamados de dentro de um **worker** (decorador `@work`). Como `_tui_confirm` era chamado diretamente do handler `on_input_submitted`, o framework lancava:

```
NoActiveWorker: push_screen must be run from a worker when `wait_for_dismiss` is True
```

Esta excecao propagava para o `except Exception` que apenas escrevia o erro no chat. Todo o output acumulado era perdido.

### Causa 2: Buffering de todas as chunks

O `on_input_submitted` acumulava TODAS as chunks num array `response_chunks` e so escrevia no final do loop do agente. Isto significava que:

- Mensagens de status (execucao de ferramenta, bloqueio) nao apareciam em tempo real
- Se uma excecao ocorresse a meio (como a do `push_screen_wait`), todo o output acumulado era descartado

## Solucao

### 1. `_tui_confirm` — callback pattern em vez de `push_screen_wait`

Substituido `self.push_screen_wait(screen)` por `self.push_screen(screen, callback=on_dismiss)` + `asyncio.Future`. O `push_screen` sem `wait_for_dismiss` nao requer worker e funciona corretamente a partir de qualquer handler async. O callback resolve o Future quando o modal e fechado.

**Ficheiro**: `tui/app.py:100-125`

### 2. Escrita imediata de mensagens meta

No loop de iteracao do gerador em `on_input_submitted`, chunks que comecam com `\n` (mensagens de ferramenta, bloqueio, sistema) sao escritas imediatamente com `log.write_stream()`. Chunks de texto normais continuam a ser acumuladas e escritas no final para evitar quebras de linha por chunk.

**Ficheiro**: `tui/app.py:193-209`

### 3. `ConfirmScreen` simplificado

O `ConfirmScreen` ja nao recebe um `Future` no construtor — usa o metodo nativo `self.dismiss(result)` do Textual. O callback passado ao `push_screen` recebe o valor do dismiss automaticamente.

**Ficheiro**: `tui/widgets/confirm_screen.py`

### 4. Teste actualizado

`test_agent_mode_allows_with_confirm` actualizado para iterar manualmente o gerador e tratar o sentinela `ConfirmationNeeded` com `asend()`, reflectindo o protocolo correcto do async generator bidirectional.

**Ficheiro**: `tests/test_agent_modes.py`

## Arquivos alterados

| Ficheiro | Alteracao |
|---|---|
| `tui/app.py` | Corrige `_tui_confirm` (callback + Future), adiciona escrita imediata de mensagens meta, importa `ConfirmationNeeded` |
| `tui/widgets/confirm_screen.py` | Remove dependencia de `asyncio.Future`, usa `dismiss(result)` nativo do Textual |
| `agent/__init__.py` | Exporta `ConfirmationNeeded` |
| `tests/test_agent_modes.py` | Actualiza teste para protocolo async generator correcto |

## Verificacao

Todos os 75 testes passam (`pipenv run pytest tests/ -v`).
