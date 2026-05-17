# Relatório de Correção — Bug de Onboarding

**Data**: 2026-05-16
**Severidade**: Crítico
**Sintoma**: Após onboarding (primeiro arranque), a app pedia e encriptava a chave da API com sucesso, mas de seguida falhava com:
```
Erro: A chave da API do DeepSeek não foi encontrada nas configurações.
```

---

## Diagnóstico

Duas causas raiz independentes:

### Causa 1 — `settings` carregado demasiado cedo

`config/settings.py` executa `settings = load_settings()` ao nível do módulo:

```python
# settings.py (linha 41)
settings = load_settings()
```

Quando o Python importa `cli.py`, a cadeia de imports é:
```
cli.py → app.py → tui/app.py → factory.py → settings.py
         ↓
   load_settings()  ←  executa aqui
```

O `load_settings()` lê `os.environ.get("DEEPSEEK_API_KEY")` — mas o CLI ainda não injetou a chave, porque `ensure_api_key()` só é chamado dentro da função `start()`, muito depois dos imports. O objeto `settings` fica com `deepseek_api_key=None` em cache.

Os providers (`DeepSeekProvider`, `OpenAIProvider`, `AnthropicProvider`) liam a chave do objeto `settings`:

```python
# Antes:
class DeepSeekProvider(BaseAIProvider):
    def __init__(self) -> None:
        if not settings.deepseek_api_key:   # ← sempre None no primeiro arranque
            raise ValueError(...)
        self.client = AsyncOpenAI(api_key=settings.deepseek_api_key, ...)
```

### Causa 2 — `.env` ficava incompleto

`_save_encrypted_api_key()` escrevia apenas a variável `*_API_KEY_ENCRYPTED=<enc>` no `.env`. As variáveis de configuração essenciais (`IA_PROVIDER`, `*_MODEL`, `LANGUAGE`) não eram escritas. Se o ficheiro fosse criado de raiz, ficava apenas com a chave encriptada.

---

## Correções Aplicadas

### 1. Providers passam a ler `os.environ` diretamente

Três ficheiros alterados:

**`providers/deepseek.py`**:
```python
# Antes: from pydeepseek_tui.config.settings import settings
# Antes: if not settings.deepseek_api_key:
# Agora:
import os
api_key = os.environ.get("DEEPSEEK_API_KEY")
base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
```

**`providers/openai.py`** — mesmo padrão para `OPENAI_API_KEY` e `OPENAI_MODEL`.
**`providers/anthropic.py`** — mesmo padrão para `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL`.

Isto elimina a dependência do `settings` em cache e garante que a chave injetada pelo CLI em `os.environ` é sempre lida corretamente, independentemente da ordem de imports.

### 2. `_save_encrypted_api_key` escreve variáveis padrão

**`cli/commands.py`** — a função `_save_encrypted_api_key()` agora escreve também:

| Variável | Valor |
|---|---|
| `IA_PROVIDER` | Provider atual (ex: `deepseek`) |
| `LANGUAGE` | `pt_BR` (ou o existente) |
| `<PREFIX>_MODEL` | Modelo padrão do provider |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` (só deepseek) |

Preserva variáveis existentes que não sejam sobrescritas pelos defaults.

### 3. Teste de factory simplificado

`tests/test_factory.py` — removido o `importlib.reload` + mock de `settings` (já não necessário).

### 4. Testes de workspace corrigidos

`tests/test_workspace.py` — session IDs agora são únicos (`uuid4().hex[:8]`) em vez de fixos, evitando contaminação entre runs.

---

## Verificação

```
$ pipenv run pytest -v
============================= 53 passed in 5.23s ==============================
```

---

## Ficheiros Alterados

| Ficheiro | Alteração |
|---|---|
| `src/pydeepseek_tui/providers/deepseek.py` | Lê `os.environ` diretamente; remove import de `settings` |
| `src/pydeepseek_tui/providers/openai.py` | Idem para OpenAI |
| `src/pydeepseek_tui/providers/anthropic.py` | Idem para Anthropic; adiciona `import os` |
| `src/pydeepseek_tui/cli/commands.py` | `_save_encrypted_api_key` escreve variáveis padrão |
| `tests/test_factory.py` | Remove `importlib.reload` e mock de settings |
| `tests/test_workspace.py` | Session IDs únicos para evitar contaminação |
