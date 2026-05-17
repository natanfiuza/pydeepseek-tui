# Relatório de Correção — Compatibilidade Textual 8.x (markup)

**Data**: 2026-05-16
**Severidade**: Crítica (impedia a execução da TUI)

---

## Sintoma

```
TypeError: RichLog.write() got an unexpected keyword argument 'markup'
```

Ao submeter uma pergunta na TUI, a aplicação quebrava com este erro.

## Causa

O projeto usa **Textual 8.2.6**. Nesta versão, `RichLog.write()` **não tem** parâmetro `markup`. A assinatura real é:

```python
RichLog.write(content, width=None, expand=False, shrink=True,
              scroll_end=None, animate=False) -> Self
```

O markup Rich é **sempre processado** quando o conteúdo é uma string — não há opção para o desligar.

Nas versões 1.x/2.x anteriores do Textual (antes do salto para 8.x), o parâmetro `markup` existia. O código original assumia essa API antiga:

```python
# Errado para Textual 8.x:
self.write(text, markup=True)    # TypeError
self.write(text, markup=False)   # TypeError
```

## Correção

**`tui/widgets/chat.py`** — Removido o parâmetro `markup` de todas as chamadas:

```python
# Antes (quebra em Textual 8.x):
def write_user_message(self, text: str) -> None:
    self.write(f"\n[bold green]Voce:[/bold green] {text}", markup=True)

# Agora (compatível com Textual 8.x):
def write_user_message(self, text: str) -> None:
    self.write(f"\n[bold green]Voce:[/bold green] {text}")
```

O `write_stream` (para chunks da IA) mantém-se com `self.write(text)` simples, sem tentar desligar o markup.

**Impacto no comportamento**: O RichLog sempre processa markup. As tags como `[bold green]` são renderizadas como cores. Se a IA produzir texto com `[palavra]`, será tratado como tag Rich. Tags desconhecidas (ex: `[Python]`, `[1]`) são inofensivas — o Rich renderiza-as como texto literal quando não encontra um estilo correspondente.

---

## Ficheiros Alterados

| Ficheiro | Alteração |
|---|---|
| `src/pydeepseek_tui/tui/widgets/chat.py` | Remove `markup=True` e `markup=False` de todas as chamadas `write()` |

## Verificação

```
$ pipenv run pytest -v
============================= 53 passed in 4.90s ==============================
```
