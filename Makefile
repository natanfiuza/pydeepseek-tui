# =============================================================================
# pydeepseek-tui — Makefile
# Uso: make <comando>
# =============================================================================

.DEFAULT_GOAL := help
SHELL         := /bin/bash
SRC_DIR       := src
TEST_DIR      := tests
PKG_NAME      := pydeepseek_tui

# Cores para output
RESET  := \033[0m
BOLD   := \033[1m
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m
RED    := \033[31m

# =============================================================================
# AJUDA
# =============================================================================
.PHONY: help
help: ## Exibe esta mensagem de ajuda
	@echo ""
	@echo "$(BOLD)$(CYAN)pydeepseek-tui — Comandos disponíveis$(RESET)"
	@echo "$(CYAN)══════════════════════════════════════════$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# INSTALAÇÃO E AMBIENTE
# =============================================================================
.PHONY: install
install: ## Instala dependências de produção via pipenv
	@echo "$(YELLOW)→ Instalando dependências...$(RESET)"
	pipenv install
	@echo "$(GREEN)✓ Dependências instaladas$(RESET)"

.PHONY: install-dev
install-dev: ## Instala todas as dependências (prod + dev) via pipenv
	@echo "$(YELLOW)→ Instalando dependências de desenvolvimento...$(RESET)"
	pipenv install --dev
	@echo "$(GREEN)✓ Dependências de desenvolvimento instaladas$(RESET)"

.PHONY: shell
shell: ## Abre o shell do ambiente virtual pipenv
	pipenv shell

.PHONY: clean-env
clean-env: ## Remove o ambiente virtual pipenv
	@echo "$(RED)→ Removendo ambiente virtual...$(RESET)"
	pipenv --rm
	@echo "$(GREEN)✓ Ambiente virtual removido$(RESET)"

# =============================================================================
# EXECUÇÃO
# =============================================================================
.PHONY: run
run: ## Executa o pydeepseek-tui (TUI completa)
	@echo "$(CYAN)→ Iniciando pydeepseek-tui...$(RESET)"
	pipenv run python -m $(PKG_NAME).main

.PHONY: dev
dev: ## Executa a TUI em modo desenvolvimento (hot-reload Textual)
	@echo "$(CYAN)→ Iniciando em modo dev (hot-reload)...$(RESET)"
	pipenv run textual run --dev $(SRC_DIR)/$(PKG_NAME)/tui/app.py

.PHONY: config
config: ## Executa o assistente de configuração interativo
	@echo "$(CYAN)→ Abrindo configuração...$(RESET)"
	pipenv run python -m $(PKG_NAME).cli.commands config

# =============================================================================
# QUALIDADE DE CÓDIGO
# =============================================================================
.PHONY: lint
lint: ## Executa o linter ruff
	@echo "$(YELLOW)→ Verificando código com ruff...$(RESET)"
	pipenv run ruff check $(SRC_DIR)/ $(TEST_DIR)/
	@echo "$(GREEN)✓ Lint concluído$(RESET)"

.PHONY: lint-fix
lint-fix: ## Corrige automaticamente os problemas do ruff
	@echo "$(YELLOW)→ Corrigindo problemas com ruff...$(RESET)"
	pipenv run ruff check --fix $(SRC_DIR)/ $(TEST_DIR)/
	@echo "$(GREEN)✓ Correções aplicadas$(RESET)"

.PHONY: format
format: ## Formata o código com black
	@echo "$(YELLOW)→ Formatando código com black...$(RESET)"
	pipenv run black $(SRC_DIR)/ $(TEST_DIR)/
	@echo "$(GREEN)✓ Formatação concluída$(RESET)"

.PHONY: format-check
format-check: ## Verifica formatação sem alterar arquivos
	@echo "$(YELLOW)→ Verificando formatação...$(RESET)"
	pipenv run black --check $(SRC_DIR)/ $(TEST_DIR)/

.PHONY: typecheck
typecheck: ## Verifica tipos com mypy
	@echo "$(YELLOW)→ Verificando tipos com mypy...$(RESET)"
	pipenv run mypy $(SRC_DIR)/
	@echo "$(GREEN)✓ Type check concluído$(RESET)"

.PHONY: check
check: lint format-check typecheck ## Executa lint + format-check + typecheck (sem alterar arquivos)
	@echo "$(GREEN)✓ Todas as verificações concluídas$(RESET)"

# =============================================================================
# TESTES
# =============================================================================
.PHONY: test
test: ## Executa todos os testes
	@echo "$(YELLOW)→ Executando testes...$(RESET)"
	pipenv run pytest $(TEST_DIR)/ -v

.PHONY: test-unit
test-unit: ## Executa apenas testes unitários
	@echo "$(YELLOW)→ Executando testes unitários...$(RESET)"
	pipenv run pytest $(TEST_DIR)/ -v -m unit

.PHONY: test-integration
test-integration: ## Executa apenas testes de integração
	@echo "$(YELLOW)→ Executando testes de integração...$(RESET)"
	pipenv run pytest $(TEST_DIR)/ -v -m integration

.PHONY: test-cov
test-cov: ## Executa testes com relatório de cobertura
	@echo "$(YELLOW)→ Executando testes com cobertura...$(RESET)"
	pipenv run pytest $(TEST_DIR)/ -v \
		--cov=$(SRC_DIR)/$(PKG_NAME) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml
	@echo "$(GREEN)✓ Relatório gerado em htmlcov/index.html$(RESET)"

.PHONY: test-watch
test-watch: ## Executa testes em modo watch (requer pytest-watch)
	pipenv run ptw $(TEST_DIR)/ -- -v

# =============================================================================
# BUILD E PUBLICAÇÃO
# =============================================================================
.PHONY: clean
clean: ## Remove artefatos de build
	@echo "$(RED)→ Limpando artefatos...$(RESET)"
	rm -rf dist/ build/ *.egg-info/ htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Limpeza concluída$(RESET)"

.PHONY: build
build: clean ## Gera os artefatos de distribuição (wheel + sdist)
	@echo "$(YELLOW)→ Gerando build...$(RESET)"
	pipenv run python -m build
	@echo "$(GREEN)✓ Build gerado em dist/$(RESET)"
	@ls -lh dist/

.PHONY: publish-test
publish-test: build ## Publica no TestPyPI
	@echo "$(YELLOW)→ Publicando no TestPyPI...$(RESET)"
	pipenv run twine check dist/*
	pipenv run twine upload --repository testpypi dist/*
	@echo "$(GREEN)✓ Publicado no TestPyPI$(RESET)"
	@echo "  Instale com: pip install --index-url https://test.pypi.org/simple/ pydeepseek-tui"

.PHONY: publish
publish: build ## Publica no PyPI oficial
	@echo "$(RED)$(BOLD)ATENÇÃO: Publicando no PyPI oficial!$(RESET)"
	@read -p "Confirma? [s/N] " ans && [ "$$ans" = "s" ] || exit 1
	pipenv run twine check dist/*
	pipenv run twine upload dist/*
	@echo "$(GREEN)✓ Publicado no PyPI$(RESET)"
	@echo "  Instale com: pip install pydeepseek-tui"

# =============================================================================
# UTILITÁRIOS
# =============================================================================
.PHONY: setup-config-dir
setup-config-dir: ## Cria o diretório de configuração ~/.deepseek-tui
	@echo "$(YELLOW)→ Criando diretório de configuração...$(RESET)"
	mkdir -p ~/.deepseek-tui/sessions
	@echo "$(GREEN)✓ Diretório ~/.deepseek-tui/ criado$(RESET)"

.PHONY: info
info: ## Exibe informações do ambiente
	@echo "$(CYAN)── Ambiente ──────────────────────$(RESET)"
	@pipenv --version
	@python --version 2>/dev/null || echo "Python não encontrado no PATH"
	@pipenv run python --version
	@echo "$(CYAN)── Pacote ────────────────────────$(RESET)"
	@echo "  Nome:    pydeepseek-tui"
	@grep '^version' pyproject.toml | head -1
	@echo "$(CYAN)── Configuração ──────────────────$(RESET)"
	@[ -f ~/.deepseek-tui/.env ] && echo "  .env:    $(GREEN)encontrado$(RESET)" || echo "  .env:    $(RED)não encontrado$(RESET) — execute: make config"

.PHONY: bump-patch
bump-patch: ## Incrementa a versão patch (0.1.0 → 0.1.1)
	@echo "$(YELLOW)→ Incrementando versão patch...$(RESET)"
	@current=$$(grep '^version' pyproject.toml | sed 's/version = "//;s/"//'); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	patch=$$(echo $$current | cut -d. -f3); \
	new="$$major.$$minor.$$((patch + 1))"; \
	sed -i "s/^version = \"$$current\"/version = \"$$new\"/" pyproject.toml; \
	echo "$(GREEN)✓ Versão: $$current → $$new$(RESET)"

.PHONY: bump-minor
bump-minor: ## Incrementa a versão minor (0.1.0 → 0.2.0)
	@echo "$(YELLOW)→ Incrementando versão minor...$(RESET)"
	@current=$$(grep '^version' pyproject.toml | sed 's/version = "//;s/"//'); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	new="$$major.$$((minor + 1)).0"; \
	sed -i "s/^version = \"$$current\"/version = \"$$new\"/" pyproject.toml; \
	echo "$(GREEN)✓ Versão: $$current → $$new$(RESET)"
