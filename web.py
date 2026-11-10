from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, List
import asyncio

from config import settings
from storage import Storage
from scraper import SIGProjScraper
from ai_filter import get_ai_engine

app = FastAPI(title="SIGProj AI - Filtro de Editais de Computação")

is_refreshing = False

def run_sync_task():
    global is_refreshing
    try:
        is_refreshing = True
        scraper = SIGProjScraper()
        storage = Storage()
        engine, model_desc = get_ai_engine()

        editais = scraper.fetch_active_editais()
        for ed in editais:
            storage.save_edital(ed)

        unanalyzed = storage.get_unanalyzed_editais()
        for ed in unanalyzed:
            try:
                analysis = engine.analyze(ed)
                storage.save_analysis(ed.id, analysis, model_desc)
            except Exception as e:
                print(f"Erro analisando edital {ed.id}: {e}")
    finally:
        is_refreshing = False

@app.get("/api/editais")
def get_editais(
    min_score: int = Query(0, ge=0, le=100),
    area: Optional[str] = None,
    only_relevant: bool = True
):
    storage = Storage()
    if only_relevant:
        items = storage.get_relevant_editais(min_score=min_score, area=area)
    else:
        items = storage.get_all_editais_full(only_active=True)

    result = []
    for item in items:
        ed = item.edital
        an = item.analysis
        result.append({
            "id": ed.id,
            "nome": ed.nome,
            "descricao": ed.descricao,
            "programa": ed.programa_nome,
            "tipo": ed.tipo_edital_nome,
            "data_abertura": ed.data_abertura,
            "data_encerramento": ed.data_encerramento,
            "dias_restantes": ed.dias_restantes,
            "link_publico": ed.link_publico,
            "publico_alvo": ed.publico_alvo,
            "anexos": [{"nome": a.nome, "url": a.url} for a in ed.anexos if a.url],
            "score": an.score if an else 0,
            "relevante": an.relevante if an else False,
            "area": an.area if an else "Não Analisado",
            "justificativa": an.justificativa if an else "",
            "tags": an.tags if an else [],
            "requisitos_destaque": an.requisitos_destaque if an else [],
            "model_used": item.model_used,
            "analyzed_at": item.analyzed_at
        })
    return result

@app.post("/api/refresh")
def trigger_refresh(background_tasks: BackgroundTasks):
    global is_refreshing
    if is_refreshing:
        return {"status": "busy", "message": "Atualização já em andamento."}
    background_tasks.add_task(run_sync_task)
    return {"status": "started", "message": "Sincronização iniciada em segundo plano."}

@app.get("/api/status")
def get_status():
    global is_refreshing
    return {"refreshing": is_refreshing}

@app.get("/", response_class=HTMLResponse)
def index_html():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIGProj AI - Editais para Computação</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: #111827;
            --surface-hover: #1f293d;
            --border: #283548;
            --text-main: #f3f4f6;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --accent: #8b5cf6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            padding: 2rem 1.5rem;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
        }

        .brand h1 {
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa 0%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand p {
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }

        .actions {
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }

        .btn {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 0.65rem 1.25rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn:hover {
            background-color: var(--primary-hover);
            transform: translateY(-1px);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Filter Controls */
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
            background-color: var(--surface);
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid var(--border);
        }

        .control-group label {
            display: block;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }

        .control-group input, .control-group select {
            width: 100%;
            background-color: var(--bg);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 0.6rem 0.8rem;
            border-radius: 6px;
            outline: none;
            font-size: 0.9rem;
        }

        .control-group input:focus, .control-group select:focus {
            border-color: var(--primary);
        }

        /* Grid of Editais */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 1.5rem;
            align-items: stretch;
        }

        .card {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-width: 0; /* Impede que o conteúdo estoure as colunas do CSS Grid */
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            overflow: hidden; /* Evita que o texto ou fontes vazem para outros cards */
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
        }

        .card:hover {
            border-color: #3b82f688;
            transform: translateY(-3px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }

        .card-body {
            min-width: 0;
            width: 100%;
            max-width: 100%;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.75rem;
            margin-bottom: 1rem;
            min-width: 0;
            width: 100%;
        }

        .score-badge {
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            white-space: nowrap;
            flex-shrink: 0;
        }

        .score-high {
            background-color: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .score-medium {
            background-color: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .score-low {
            background-color: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .area-pill {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 600;
            color: #c084fc;
            background-color: rgba(192, 132, 252, 0.1);
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            margin-bottom: 0.5rem;
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .card-title {
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.45;
            color: var(--text-main);
            margin-bottom: 0.85rem;
            min-width: 0;
            width: 100%;
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
            word-wrap: break-word;
            white-space: normal;
            hyphens: auto;
        }

        .ai-box {
            background-color: rgba(0, 0, 0, 0.25);
            border-left: 3px solid var(--accent);
            padding: 0.75rem;
            border-radius: 0 6px 6px 0;
            font-size: 0.85rem;
            color: #cbd5e1;
            margin-bottom: 1rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .ai-box strong {
            color: #a78bfa;
            display: block;
            margin-bottom: 0.25rem;
        }

        .tags-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 1.25rem;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .tag {
            font-size: 0.7rem;
            background-color: var(--surface-hover);
            color: var(--text-muted);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.75rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-size: 0.85rem;
            min-width: 0;
        }

        .deadline {
            color: var(--text-muted);
        }

        .deadline.urgent {
            color: #f87171;
            font-weight: 700;
        }

        .card-link {
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }

        .card-link:hover {
            text-decoration: underline;
        }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 4rem 1rem;
            color: var(--text-muted);
        }

        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>SIGProj AI Scanner</h1>
                <p>Oportunidades, bolsas e editais filtrados com IA para estudantes de Computação</p>
            </div>
            <div class="actions">
                <button id="refreshBtn" class="btn" onclick="triggerRefresh()">
                    <span id="btnIcon">🔄</span>
                    <span id="btnText">Atualizar SIGProj & IA</span>
                </button>
            </div>
        </header>

        <section class="controls">
            <div class="control-group">
                <label for="search">Buscar no título ou justificativa</label>
                <input type="text" id="search" placeholder="Ex: hackathon, FACOM, bolsa..." oninput="renderEditais()">
            </div>
            <div class="control-group">
                <label for="areaFilter">Área</label>
                <select id="areaFilter" onchange="renderEditais()">
                    <option value="">Todas as Áreas</option>
                    <option value="Desenvolvimento de Software">Desenvolvimento de Software</option>
                    <option value="Inteligência Artificial & Dados">Inteligência Artificial & Dados</option>
                    <option value="Inovação & Hackathons">Inovação & Hackathons</option>
                    <option value="Iniciação Científica & Pesquisa">Iniciação Científica & Pesquisa</option>
                    <option value="Bolsas & Extensão">Bolsas & Extensão</option>
                </select>
            </div>
            <div class="control-group">
                <label for="minScore">Score Mínimo da IA (<span id="scoreVal">60</span>/100)</label>
                <input type="range" id="minScore" min="0" max="100" value="60" oninput="document.getElementById('scoreVal').innerText=this.value; renderEditais()">
            </div>
            <div class="control-group">
                <label for="sortOrder">Ordenar por</label>
                <select id="sortOrder" onchange="renderEditais()">
                    <option value="score_desc">Maior Relevância (Score IA)</option>
                    <option value="deadline_asc">Prazo Mais Próximo</option>
                </select>
            </div>
        </section>

        <main class="grid" id="editaisGrid">
            <div class="empty-state">Carregando editais...</div>
        </main>
    </div>

    <script>
        let allEditais = [];

        async function fetchEditais() {
            try {
                const res = await fetch('/api/editais?only_relevant=false');
                allEditais = await res.json();
                renderEditais();
            } catch (err) {
                document.getElementById('editaisGrid').innerHTML = '<div class="empty-state">Erro ao carregar editais. Verifique a conexão com o servidor.</div>';
            }
        }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function renderEditais() {
            const grid = document.getElementById('editaisGrid');
            const search = document.getElementById('search').value.toLowerCase();
            const area = document.getElementById('areaFilter').value;
            const minScore = parseInt(document.getElementById('minScore').value, 10);
            const sortOrder = document.getElementById('sortOrder').value;

            let filtered = allEditais.filter(ed => {
                if (ed.score < minScore) return false;
                if (area && ed.area !== area) return false;
                if (search) {
                    const text = `${ed.nome} ${ed.descricao} ${ed.justificativa} ${(ed.tags || []).join(' ')}`.toLowerCase();
                    if (!text.includes(search)) return false;
                }
                return true;
            });

            if (sortOrder === 'score_desc') {
                filtered.sort((a, b) => b.score - a.score);
            } else if (sortOrder === 'deadline_asc') {
                filtered.sort((a, b) => {
                    const da = a.dias_restantes ?? 999;
                    const db = b.dias_restantes ?? 999;
                    return da - db;
                });
            }

            if (filtered.length === 0) {
                grid.innerHTML = '<div class="empty-state">Nenhum edital encontrado com os filtros selecionados. Diminua o score mínimo ou limpe a busca.</div>';
                return;
            }

            grid.innerHTML = filtered.map(ed => {
                let scoreClass = 'score-low';
                if (ed.score >= 80) scoreClass = 'score-high';
                else if (ed.score >= 60) scoreClass = 'score-medium';

                let deadlineHtml = '';
                if (ed.dias_restantes !== null) {
                    const isUrgent = ed.dias_restantes <= 5;
                    deadlineHtml = `<span class="deadline ${isUrgent ? 'urgent' : ''}">⏳ ${ed.dias_restantes} dias restantes</span>`;
                } else {
                    deadlineHtml = '<span class="deadline">Prazo N/A</span>';
                }

                const tagsHtml = (ed.tags || []).map(t => `<span class="tag">#${escapeHtml(t)}</span>`).join('');
                
                let anexosHtml = '';
                if (ed.anexos && ed.anexos.length > 0) {
                    anexosHtml = `
                    <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px dashed var(--border); font-size: 0.8rem; overflow-wrap: anywhere;">
                        <span style="color: var(--text-muted); font-weight: 600;">📎 Documentos / PDFs:</span>
                        <div style="margin-top: 0.35rem; display: flex; flex-direction: column; gap: 0.3rem;">
                            ${ed.anexos.map(a => `
                                <a href="${encodeURI(a.url)}" target="_blank" rel="noopener" style="color: #60a5fa; text-decoration: none; display: flex; align-items: flex-start; gap: 0.3rem; word-break: break-word; overflow-wrap: anywhere;">
                                    <span>📄</span> <span>${escapeHtml(a.nome)}</span>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                    `;
                }

                const safeUrl = encodeURI(ed.link_publico);

                return `
                <div class="card">
                    <div class="card-body">
                        <div class="card-header">
                            <span class="area-pill">${escapeHtml(ed.area || 'Geral')}</span>
                            <span class="score-badge ${scoreClass}">${ed.score} pts</span>
                        </div>
                        <h2 class="card-title">${escapeHtml(ed.nome)}</h2>
                        ${ed.justificativa ? `
                        <div class="ai-box">
                            <strong>💡 Parecer da IA:</strong>
                            ${escapeHtml(ed.justificativa)}
                        </div>` : ''}
                        <div class="tags-container">
                            ${tagsHtml}
                        </div>
                        ${anexosHtml}
                    </div>
                    <div class="card-footer">
                        ${deadlineHtml}
                        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
                            <button data-url="${safeUrl}" onclick="copyLink(this.dataset.url, this)" style="background: var(--surface-hover); border: 1px solid var(--border); color: var(--text-main); font-size: 0.8rem; padding: 0.35rem 0.65rem; border-radius: 6px; cursor: pointer; white-space: nowrap;">
                                📋 Copiar Link
                            </button>
                            <a href="${safeUrl}" target="_blank" rel="noopener" class="card-link" style="font-size: 0.85rem; white-space: nowrap;">
                                Ver no SIGProj ↗
                            </a>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }

        function copyLink(url, btn) {
            navigator.clipboard.writeText(url).then(() => {
                const originalText = btn.innerText;
                btn.innerText = '✅ Copiado!';
                btn.style.borderColor = '#10b981';
                btn.style.color = '#34d399';
                setTimeout(() => {
                    btn.innerText = originalText;
                    btn.style.borderColor = 'var(--border)';
                    btn.style.color = 'var(--text-main)';
                }, 2000);
            }).catch(err => {
                prompt('Link do Edital:', url);
            });
        }

        async function triggerRefresh() {
            const btn = document.getElementById('refreshBtn');
            const icon = document.getElementById('btnIcon');
            const text = document.getElementById('btnText');
            btn.disabled = true;
            icon.className = 'spinner';
            icon.innerText = '';
            text.innerText = 'Processando com IA...';

            try {
                await fetch('/api/refresh', { method: 'POST' });
                pollStatus();
            } catch (err) {
                alert('Erro ao iniciar atualização: ' + err);
                resetBtn();
            }
        }

        function resetBtn() {
            const btn = document.getElementById('refreshBtn');
            const icon = document.getElementById('btnIcon');
            const text = document.getElementById('btnText');
            btn.disabled = false;
            icon.className = '';
            icon.innerText = '🔄';
            text.innerText = 'Atualizar SIGProj & IA';
        }

        async function pollStatus() {
            const interval = setInterval(async () => {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (!data.refreshing) {
                    clearInterval(interval);
                    resetBtn();
                    await fetchEditais();
                }
            }, 2000);
        }

        fetchEditais();
    </script>
</body>
</html>
"""
