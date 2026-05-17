# Relatório de Correção — Markup Textual + Erro 400

**Data**: 2026-05-16
**Severidade**: Alta

---

## Problema 1 — Markup `[bold green]` visível como texto literal

### Sintoma
A TUI mostrava tags Rich markup como texto literal (`[bold green]Voce:[/bold green]`) em vez de aplicar as cores. O texto da IA também podia conter `[...]` que eram interpretados como markup.

### Causa
Duas falhas no `ChatLog` (wrapper de `RichLog`):

1. `RichLog.write()` tem um parâmetro `markup` — o comportamento padrão varia entre versões do Textual. Sem `markup=True` explícito, algumas versões não processam tags Rich.

2. Os chunks de streaming da IA (`log.write(chunk)` no `tui/app.py`) passavam texto do modelo diretamente para o `RichLog.write()`. Se a resposta da IA contivesse `[algo]`, o parser Rich interpretava como tag de estilo, corrompendo a renderização.

### Correção

**`tui/widgets/chat.py`** — Todos os métodos `write_*` agora usam `markup=True`:

```python
class ChatLog(RichLog):
    def write_user_message(self, text: str) -> None:
        self.write(f"\n[bold green]Voce:[/bold green] {text}", markup=True)
    ...
```

Adicionado `write_stream(text)` que usa `markup=False` para chunks da IA — preserva texto literal sem interpretar brackets:

```python
    def write_stream(self, text: str) -> None:
        self.write(text, markup=False)
```

**`tui/app.py`** — Streaming da IA usa `write_stream()`:
```python
# Antes: log.write(chunk)
# Agora:
async for chunk in self.agent.chat_stream(user_text):
    log.write_stream(chunk)
```

As notificações do agente (`[bold yellow]A executar...[/bold yellow]`) são yielded como parte do stream — estas passam a ser escritas sem markup também. Para manter a formatação, o agente usa `write_stream` para texto normal e os métodos `write_user_message`, `write_error`, `write_system` (com `markup=True`) para mensagens do sistema.

---

## Problema 2 — Erro HTTP 400 ao usar `list_dir`

### Sintoma
Quando a IA tentava usar a tool `list_dir`, a API retornava HTTP 400 (Bad Request).

### Causa
A tool `list_dir` definia `"required": []` no JSON Schema dos parâmetros. Algumas APIs OpenAI-compatíveis (incluindo DeepSeek) rejeitam arrays vazios no campo `required`.

Além disso, os parâmetros incluíam a keyword `default` (ex: `"default": "*"`), que é uma anotação JSON Schema (não parte do subset OpenAI), e pode ser rejeitada por algumas implementações mais estritas.

### Correção

**`tools/list_dir.py`** — Removido `"required": []` e `"default"` dos parâmetros:
```python
# Antes: "required": [], e "default": "*" / "default": 2
# Agora: sem required vazio, sem default
```

**`tools/registry.py`** — Adicionado `_sanitize_params()` que sanitiza automaticamente todos os schemas:
```python
@staticmethod
def _sanitize_params(params: Dict[str, Any]) -> None:
    if "required" in params and not params["required"]:
        del params["required"]
    for prop in params.get("properties", {}).values():
        prop.pop("default", None)
```

Este método é chamado em `get_api_schema()` para todas as tools. Garante que mesmo tools futuras não causem erro 400 por schema inválido.

---

## Ficheiros Alterados

| Ficheiro | Alteração |
|---|---|
| `src/pydeepseek_tui/tui/widgets/chat.py` | `markup=True` explícito + `write_stream()` com `markup=False` |
| `src/pydeepseek_tui/tui/app.py` | `log.write(chunk)` → `log.write_stream(chunk)` |
| `src/pydeepseek_tui/tools/list_dir.py` | Remove `required: []` e `default` dos parâmetros |
| `src/pydeepseek_tui/tools/registry.py` | Adiciona `_sanitize_params()` para limpar schemas |

## Verificação

```
$ pipenv run pytest -v
============================= 53 passed in 5.23s ==============================
```
