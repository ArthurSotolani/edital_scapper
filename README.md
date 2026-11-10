# 🎯 SIGProj AI Scrapper & Filter

> Sistema inteligente de raspagem, análise e filtragem de editais do **SIGProj** com **Inteligência Artificial**, focado em encontrar oportunidades relevantes para estudantes de **Computação / TI** (Ciência da Computação, Engenharia de Software, Sistemas de Informação, Ciência de Dados, Engenharia da Computação, etc.).

---

## ⚠️ Configuração da Chave de API (Aviso Importante)

> [!IMPORTANT]
> **Onde configurar sua chave de IA:**
> O arquivo `.env` na raiz do projeto controla qual IA fará a análise dos editais. 
> 
> 1. Copie o arquivo de exemplo para criar o seu `.env`:
>    ```bash
>    cp .env.example .env
>    ```
> 2. Abra o arquivo `.env` e preencha o campo **`GEMINI_API_KEY`**:
>    ```ini
>    AI_PROVIDER=gemini
>    GEMINI_API_KEY=coloque_sua_chave_aqui
>    GEMINI_MODEL=gemini-2.5-flash
>    MIN_RELEVANCE_SCORE=60
>    ```
> 3. **Onde obter a chave gratuita:** Você pode gerar uma chave gratuita em segundos no [Google AI Studio](https://aistudio.google.com/).

> [!TIP]
> **Funciona mesmo sem chave de API:**
> Se você executar o sistema sem preencher a chave, ele **não vai quebrar**. O sistema ativará automaticamente o **motor heurístico inteligente** baseado em regras e termos acadêmicos da UFMS/FACOM/TI. Assim que você colocar a chave no `.env`, ele passará a usar o modelo generativo completo.

> [!NOTE]
> **Outros provedores suportados:** Você também pode usar OpenAI, Groq ou Ollama local bastando alterar `AI_PROVIDER=openai` e preenchendo `OPENAI_API_KEY` no mesmo arquivo.

---

## 🚀 Instalação Rápida

O ambiente virtual `venv` já está configurado no projeto. Para utilizá-lo:

```bash
# 1. Acesse o diretório do projeto
cd /home/arthur-sotolani/dev/edital_scrapper

# 2. Ative o ambiente virtual
source venv/bin/activate

# 3. (Opcional) Caso precise reinstalar as dependências:
pip install -r requirements.txt
```

---

## 💻 Instruções de Uso

Todas as ações podem ser executadas pelo comando principal `python main.py`:

### 1. Coletar editais e classificar com IA (`fetch`)
Conecta à API oficial do SIGProj, busca todos os editais vigentes e executa a IA sobre os novos editais encontrados:
```bash
python main.py fetch
```
*Opções:*
- `--limit 10`: Limita o número de editais baixados para testes rápidos.
- `--force`: Força a reanálise de todos os editais, inclusive os já analisados.

---

### 2. Listar editais relevantes (`list`)
Exibe uma tabela colorida no terminal com os editais que a IA considerou pertinentes:
```bash
python main.py list
```
*Opções de filtro:*
- `python main.py list -l` ou `--links`: Exibe uma coluna dedicada com o link direto de cada edital.
- `python main.py list --min-score 80`: Mostra apenas editais com relevância altíssima (80+).
- `python main.py list --area "Hackathons"`: Filtra por área específica.
- `python main.py list --all`: Mostra todos os editais cadastrados (inclusive os descartados).

---

### 3. Obter o Link do Edital (`link`)
Obtém o link direto para a página do SIGProj ou para os arquivos PDF do edital:
```bash
# Exibe os links da página oficial e de todos os anexos/PDFs:
python main.py link 181266305

# Exibe apenas a URL pura (ideal para scripts bash ou copiar para a área de transferência):
python main.py link 181266305 --only-url

# Abre o edital diretamente no seu navegador padrão:
python main.py link 181266305 --open

# Obtém o link direto para download do arquivo PDF do edital:
python main.py link 181266305 --pdf
```

---

### 4. Exibir detalhes completos de um edital (`show`)
Apresenta o relatório detalhado do edital, com o **parecer da IA**, **justificativa**, **tags**, contagem regressiva de encerramento e **links para download de anexos**:
```bash
python main.py show <ID_DO_EDITAL>
```
*Exemplo prático:*
```bash
python main.py show 181266305
```

---

### 4. Iniciar o Painel Web Interativo (`web`)
Inicia uma interface gráfica no navegador com cartões, filtros rápidos e botão de atualização em segundo plano:
```bash
python main.py web
```
Depois abra no seu navegador: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

### 5. Exportar relatórios (`export`)
Gera arquivos prontos para compartilhar ou consultar offline:
```bash
# Exportar em Markdown
python main.py export --format md --output editais_relevantes.md

# Exportar em CSV (para abrir no Excel / Google Planilhas)
python main.py export --format csv --output editais.csv

# Exportar em JSON
python main.py export --format json --output editais.json
```

---

## 🧠 Critérios de Pontuação da IA (Score 0 a 100)

| Score | Nível | O que significa para o estudante de Computação |
|---|:---:|---|
| **85 a 100** | **Alta Relevância** | Vagas e editais da **FACOM**, DTI, AGETEC; **Hackathons**; Bolsas de desenvolvimento web/mobile, sistemas, IA, automação e Iniciação Tecnológica (**PIBITI/PIVIC**). |
| **60 a 84** | **Média Relevância** | Editais de empresas juniores, inovação, patentes e programas multidisciplinares que incluem tecnologia (ex: **PET-Saúde Digital**). |
| **30 a 59** | **Baixa Relevância** | Editais gerais da universidade onde TI tem aplicação muito marginal. |
| **0 a 29** | **Irrelevante** | Editais restritos a cursos de outras áreas (Medicina, Odontologia, Letras, etc.) ou processos internos de servidores docentes (PGD) sem vagas para alunos. |

---

## 📁 Estrutura de Arquivos

```
edital_scrapper/
├── main.py             # Entrada principal do CLI
├── cli.py              # Comandos e formatação no terminal com a lib Rich
├── scraper.py          # Conexão direta com a API pública REST do SIGProj
├── ai_filter.py        # Motores de IA (Gemini, OpenAI/Groq/Ollama, Heurístico)
├── storage.py          # Banco SQLite local com cache de análises
├── models.py           # Modelos de dados e validações (Pydantic)
├── web.py              # Servidor Web FastAPI e Dashboard HTML/CSS moderno
├── config.py           # Carregamento do arquivo .env e configurações
├── requirements.txt    # Lista de dependências Python
├── .env.example        # Arquivo de exemplo com os campos de API
└── README.md           # Este manual de instruções
```
