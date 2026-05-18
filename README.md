# PyDeepSeek TUI

Interface de terminal (TUI) moderna, assíncrona e multi-provedor para interagir com IAs como DeepSeek, OpenAI e Anthropic. Construída com Python e Textual.

## Funcionalidades

- **Multi-provedor** — suporte a DeepSeek, OpenAI e Anthropic com seleção por linha de comando ou configuração
- **Function Calling** — agente autónomo capaz de ler/escrever ficheiros, executar comandos shell, pesquisar na web, extrair texto de URLs, listar diretórios, pesquisar em ficheiros e operações git
- **Modos de operação** — Plan (leitura), Agent (confirmação de ações destrutivas) e YOLO (execução automática)
- **Interface rica no terminal** — construída com Textual 8.x, com suporte a cores, scroll e atalhos de teclado
- **Rastreio de sessão** — cada execução gera um registo persistente com contagem de tokens, custos em USD e logs de interação
- **Encriptação da chave API** — chave protegida com PBKDF2 + Fernet (via `cryptography`)
- **Internacionalização** — suporte a Português (Brasil) e Inglês
- **Segurança** — sandbox de ficheiros que restringe operações ao diretório de trabalho

## Instalação

Requer Python 3.13+.

```bash
pip install pydeepseek-tui
```

Na primeira execução, o sistema pede a chave da API e guarda-a encriptada em `~/.deepseek-tui/.env`.

### Instalação para desenvolvimento

```bash
git clone https://github.com/natanfiuza/pydeepseek-tui.git
cd pydeepseek-tui
pipenv install --dev
```

## Uso

```bash
# Iniciar com o provedor padrão (deepseek)
pydeepseek start

# Escolher provedor
pydeepseek start --provider openai
pydeepseek start --provider anthropic

# Escolher modelo e modo
pydeepseek start --provider deepseek --model deepseek-v4 --mode yolo

# Escolher idioma
pydeepseek start --lang en_US

# Assistente de configuração interativo
pydeepseek config

# Listar sessões salvas
pydeepseek sessions
```

### Atalhos de teclado

| Tecla | Ação |
|-------|------|
| `q` | Sair (guarda a sessão) |
| `c` | Limpar o chat |
| `m` | Alternar modo (Plan → Agent → YOLO) |

### Modos de operação

| Modo | Comportamento |
|------|---------------|
| **Plan** | Apenas ferramentas de leitura. Bloqueia shell, escrita e git. |
| **Agent** | Pergunta antes de executar ferramentas destrutivas via modal interativo. |
| **YOLO** | Executa todas as ferramentas sem confirmação. |

## Dependências

O projeto utiliza as seguintes bibliotecas:

### Runtime

| Biblioteca | Versão | Uso |
|------------|--------|-----|
| [textual](https://github.com/Textualize/textual) | 8.x | Framework TUI |
| [openai](https://github.com/openai/openai-python) | 2.x | Cliente para DeepSeek e OpenAI |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | 0.x | Cliente para Anthropic |
| [httpx](https://github.com/encode/httpx) | 0.x | HTTP client para web tools |
| [cryptography](https://github.com/pyca/cryptography) | 48.x | Encriptação da chave API |
| [click](https://github.com/pallets/click) | 8.x | CLI |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.x | Leitura do ficheiro `.env` |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | 4.x | Extração de texto de URLs |
| [duckduckgo-search](https://github.com/deedy5/duckduckgo_search) | 8.x | Pesquisa web |

### Desenvolvimento

| Ferramenta | Uso |
|------------|-----|
| [pipenv](https://github.com/pypa/pipenv) | Gestão de ambiente virtual e dependências |
| [pytest](https://github.com/pytest-dev/pytest) | Testes automatizados |
| [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Suporte a testes assíncronos |
| [pytest-cov](https://github.com/pytest-dev/pytest-cov) | Cobertura de testes |
| [ruff](https://github.com/astral-sh/ruff) | Linting e formatação |
| [black](https://github.com/psf/black) | Formatação de código |
| [mypy](https://github.com/python/mypy) | Verificação de tipos |

## Desenvolvimento

```bash
# Instalar dependências de desenvolvimento
make dev

# Executar testes
make test

# Linting
make lint

# Formatação automática
make format

# Construir distribuição
make build
```

### Estrutura do projeto

```
pydeepseek-tui/
├── src/pydeepseek_tui/
│   ├── agent/          # Loop do agente, modos, sessões, activity logger
│   ├── cli/            # Comandos CLI (click)
│   ├── config/         # Settings, encriptação, debug logger
│   ├── i18n/           # Traduções (pt_BR, en_US)
│   ├── providers/      # DeepSeek, OpenAI, Anthropic
│   ├── tools/          # Ferramentas do agente (8 tools)
│   └── tui/            # Interface Textual (app, widgets, screens)
├── tests/              # Testes automatizados
├── Makefile            # Comandos de desenvolvimento
└── pyproject.toml      # Configuração do projeto
```

## Contribuição

Contribuições são bem-vindas. Para contribuir:

1. Faz um fork do repositório
2. Cria um branch para a tua feature (`git checkout -b feature/nova-funcionalidade`)
3. Instala o ambiente de desenvolvimento (`pipenv install --dev`)
4. Faz as alterações e garante que os testes passam (`make test`)
5. Verifica a formatação (`make lint`)
6. Submete um pull request

Antes de submeter, confirma que:

- [ ] Testes novos cobrem a funcionalidade adicionada
- [ ] `make lint` não reporta erros
- [ ] `make test` passa com sucesso
- [ ] O código segue o estilo do projeto (black + ruff)

## Agradecimentos

Este projeto é mantido por **Nataniel Fiuza** — obrigado por usar o PyDeepSeek TUI.

- **Email:** [contato@natanfiuza.dev.br](mailto:contato@natanfiuza.dev.br)
- **GitHub:** [github.com/natanfiuza](https://github.com/natanfiuza)

Se o projeto te foi útil, deixa uma estrela no repositório.
