# Relatório: Correção do travamento do modal de confirmação

**Data**: 2026-05-18
**Branch**: develop_natan
**Issue**: Modal de confirmação (ConfirmScreen) trava ao abrir, impedindo interação e saída da aplicação

## Causa raiz

O `push_screen` do Textual era chamado **de dentro do async generator** `chat_stream()`, que por sua vez era iterado pelo handler `on_input_submitted`. O call stack era:

```
on_input_submitted → chat_stream.__anext__ → ... → _check_confirmation → _tui_confirm → push_screen
```

Esta cadeia de chamadas dentro do estado interno do async generator conflitua com o event loop do Textual, causando deadlock: o modal aparece mas nunca recebe eventos de teclado/mouse.

## Solução final

Refatoração estrutural: o async generator `chat_stream` agora **cede** (`yield`) um sentinela `ConfirmationNeeded` em vez de chamar `push_screen` internamente. Quem itera o gerador (`on_input_submitted`) trata a confirmação **fora** do gerador e envia o resultado de volta com `asend()`.

### Fluxo antes (quebrado):
```
chat_stream → await _check_confirmation() → push_screen DENTRO do gerador
```

### Fluxo depois (corrigido):
```
chat_stream → yield ConfirmationNeeded  ← gerador suspenso aqui
on_input_submitted → detecta sentinela → _tui_confirm → push_screen FORA do gerador
on_input_submitted → asend(result) → gerador continua
```

### Arquivos alterados

1. **`agent/loop.py`**:
   - Nova classe `ConfirmationNeeded(tool_name, args)` — sentinela para pedidos de confirmação
   - `chat_stream` agora cede `ConfirmationNeeded` em vez de chamar `_check_confirmation` para ferramentas destrutivas em modo AGENT
   - Tipo de retorno: `AsyncGenerator[str | ConfirmationNeeded, bool]`

2. **`tui/app.py`**:
   - `on_input_submitted` itera manualmente o gerador com `__anext__()`/`asend()` em vez de `async for`
   - `ConfirmationNeeded` é tratado fora do gerador, chamando `_tui_confirm` diretamente
   - `_tui_confirm` usa `run_worker` + `push_screen(wait_for_dismiss=True)` — o padrão oficial do Textual

3. **`tui/widgets/confirm_screen.py`**:
   - Simplificado: sem `Future` customizado, sem método `_finish`
   - Ações chamam `self.dismiss(result)` diretamente

4. **`agent/__init__.py`**:
   - Exporta `ConfirmationNeeded`

### Porquê isto resolve

- `push_screen` já não é chamado de dentro do estado interno do async generator
- O event loop do Textual pode processar corretamente o `ScreenResume` do modal
- Os eventos de teclado/mouse chegam ao modal
