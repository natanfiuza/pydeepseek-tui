# Bugfix: Modal de Confirmação — 2026-05-17

Branch: `main`

## Problemas corrigidos

1. **Modal travava e não fechava** — Substituído `ModalScreen` por `Screen` com `app.pop_screen()` explícito. Adicionado handler `on_key` para atalhos de teclado e `escape` para fechar.

2. **Texto "Desejas permitir esta operacao?"** → **"Permite executar esta operacao?"**

3. **Atalhos de teclado** nos botões: `(S)im`, `Sim para (T)odos`, `(N)ao` — teclas `s`, `t`, `n` + `Escape` para cancelar.

4. **Cor do botão Sim** alterada para verde (`background: green 30%`).

5. **debug.log com chunks quebrados** — OUTPUT agora é acumulado e gravado como resposta completa.

## Ficheiros alterados
- `tui/widgets/confirm_screen.py` — reescrito: `Screen` em vez de `ModalScreen`, `on_key`, `_finish()`, CSS verde
- `tui/app.py` — `_tui_confirm` simplificado, debug output acumulado

## Testes
75 passam. ruff limpo. black formatado.
