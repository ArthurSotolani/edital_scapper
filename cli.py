import argparse
import sys
import csv
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint

from config import settings
from scraper import SIGProjScraper
from storage import Storage
from ai_filter import get_ai_engine
from models import EditalFull

console = Console()

def cmd_fetch(args):
    """Busca editais no SIGProj e classifica com IA."""
    console.print("\n[bold cyan]🔍 Conectando à API do SIGProj...[/bold cyan]")
    scraper = SIGProjScraper()
    storage = Storage()
    engine, model_desc = get_ai_engine()

    console.print(f"[dim]Motor de Análise:[/dim] [green]{model_desc}[/green]")
    if "heuristic" in model_desc:
        console.print("[yellow]⚠️  Dica: Defina GEMINI_API_KEY no arquivo .env para análise com LLM Gemini 2.5 Flash![/yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("Baixando editais vigentes...", total=None)
        editais = scraper.fetch_active_editais(max_items=args.limit)
        progress.update(task1, completed=1, description=f"Obtidos {len(editais)} editais do SIGProj.")

    console.print(f"📦 Salvando [bold]{len(editais)}[/bold] editais no banco local...")
    for ed in editais:
        storage.save_edital(ed)

    # Identifica os que ainda não foram analisados ou se o usuário passou --force
    unanalyzed = storage.get_unanalyzed_editais() if not args.force else editais
    console.print(f"🧠 Editais pendentes de análise por IA: [bold]{len(unanalyzed)}[/bold]\n")

    if not unanalyzed:
        console.print("[green]✨ Todos os editais vigentes já foram analisados pela IA anteriormente![/green]")
        console.print("Execute [bold]python main.py list[/bold] para visualizá-los.\n")
        return

    newly_analyzed = []
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Classificando com IA...", total=len(unanalyzed))
        for ed in unanalyzed:
            try:
                analysis = engine.analyze(ed)
                storage.save_analysis(ed.id, analysis, model_desc)
                newly_analyzed.append((ed, analysis))
            except Exception as e:
                console.print(f"[red]Erro ao analisar edital {ed.id}: {e}[/red]")
            finally:
                progress.advance(task)

    # Mostra resumo dos recém-analisados
    console.print("\n[bold green]✅ Análise concluída com sucesso![/bold green]\n")
    _display_summary(newly_analyzed)

def _display_summary(analyzed_list):
    table = Table(title="📊 Editais Analisados", show_lines=True)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Área", style="magenta", width=22)
    table.add_column("Título", style="white")
    table.add_column("Prazo", style="yellow", justify="center", width=12)

    for ed, an in analyzed_list:
        score_style = "bold green" if an.score >= 80 else ("bold yellow" if an.score >= 60 else "dim red")
        dias = ed.dias_restantes
        prazo_str = f"{dias}d restantes" if dias is not None else "Encerrado/N/A"
        
        table.add_row(
            str(ed.id),
            f"[{score_style}]{an.score}[/{score_style}]",
            an.area,
            ed.nome[:75] + ("..." if len(ed.nome) > 75 else ""),
            prazo_str
        )

    console.print(table)
    console.print("\nUse [bold cyan]python main.py show <ID>[/bold cyan] para ver a justificativa detalhada de um edital.")

def cmd_list(args):
    """Lista editais relevantes salvos."""
    storage = Storage()
    if args.all:
        items = storage.get_all_editais_full(only_active=not args.include_closed)
    else:
        items = storage.get_relevant_editais(
            min_score=args.min_score,
            area=args.area,
            only_active=not args.include_closed
        )

    if not items:
        console.print("[yellow]Nenhum edital encontrado com os filtros atuais.[/yellow]")
        console.print("Tente executar [bold]python main.py fetch[/bold] para baixar os editais do SIGProj.\n")
        return

    table = Table(
        title=f"🎯 Editais Relevantes para Estudante de Computação (Total: {len(items)})",
        show_lines=True
    )
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Área", style="magenta", width=22)
    table.add_column("Título e Tags", style="white")
    if getattr(args, "links", False):
        table.add_column("Link SIGProj", style="underline blue")
    table.add_column("Prazo", style="yellow", justify="center", width=14)

    for item in items:
        ed = item.edital
        an = item.analysis

        score_text = "-"
        area_text = "-"
        tags_text = ""

        if an:
            score_style = "bold green" if an.score >= 80 else ("bold yellow" if an.score >= 60 else "dim red")
            score_text = f"[{score_style}]{an.score}[/{score_style}]"
            area_text = an.area
            if an.tags:
                tags_text = "\n[dim]" + " • ".join(f"#{t}" for t in an.tags[:4]) + "[/dim]"

        dias = ed.dias_restantes
        if dias is not None:
            prazo_text = f"[bold green]{dias} dias[/bold green]" if dias > 5 else f"[bold red]{dias} dias![/bold red]"
        else:
            prazo_text = "[dim]N/A[/dim]"

        titulo_fmt = f"[link={ed.link_publico}][bold]{ed.nome}[/bold][/link]{tags_text}"

        row_args = [
            str(ed.id),
            score_text,
            area_text,
            titulo_fmt,
        ]
        if getattr(args, "links", False):
            row_args.append(ed.link_publico)
        row_args.append(prazo_text)

        table.add_row(*row_args)

    console.print(table)
    console.print("\n[dim]Para obter o link direto: [bold]python main.py link <ID>[/bold] | Detalhes: [bold]python main.py show <ID>[/bold][/dim]\n")

def cmd_link(args):
    """Exibe e opcionalmente abre os links do edital (página pública e PDFs)."""
    import webbrowser
    storage = Storage()
    scraper = SIGProjScraper()
    item = storage.get_edital_full(args.id)

    if not item:
        console.print(f"[red]Edital com ID {args.id} não encontrado no banco local.[/red]")
        return

    ed = item.edital
    link_publico = ed.link_publico

    # Se o usuário só quer o link puro (para scripts/clipboard)
    if args.only_url:
        print(link_publico)
        return

    anexos = ed.anexos
    if not anexos:
        anexos = scraper.fetch_edital_files(ed.id)

    primeiro_pdf = None
    for a in anexos:
        if a.url:
            primeiro_pdf = a.url
            break

    if args.pdf:
        if primeiro_pdf:
            if args.only_url:
                print(primeiro_pdf)
                return
            if args.open:
                webbrowser.open(primeiro_pdf)
                console.print(f"[green]🌐 Abrindo anexo no navegador:[/green] {primeiro_pdf}")
                return
            console.print(f"[bold cyan]Link do Arquivo/PDF:[/bold cyan] {primeiro_pdf}")
        else:
            console.print("[yellow]Nenhum arquivo PDF anexado encontrado para este edital.[/yellow]")
        return

    if args.open:
        webbrowser.open(link_publico)
        console.print(f"[green]🌐 Abrindo edital no navegador:[/green] {link_publico}")
        return

    # Visualização detalhada de links
    console.print(Panel(
        f"[bold white]{ed.nome}[/bold white]\n\n"
        f"[bold cyan]🔗 Link Oficial no SIGProj:[/bold cyan]\n"
        f"[underline blue]{link_publico}[/underline blue]",
        title=f"🌐 Links do Edital #{ed.id}",
        border_style="cyan"
    ))

    if anexos:
        console.print("[bold]📎 Documentos e Anexos para Download:[/bold]")
        for a in anexos:
            console.print(f"  • [white]{a.nome}[/white]")
            console.print(f"    [dim underline blue]{a.url}[/dim underline blue]")
    else:
        console.print("[dim]Nenhum anexo adicional listado.[/dim]")

    console.print("\n[dim]Dica: use [bold]python main.py link <ID> --open[/bold] para abrir direto no navegador.[/dim]\n")

def cmd_show(args):
    """Exibe os detalhes de um edital e a análise da IA."""
    storage = Storage()
    scraper = SIGProjScraper()
    item = storage.get_edital_full(args.id)

    if not item:
        console.print(f"[red]Edital com ID {args.id} não encontrado no banco local.[/red]")
        return

    ed = item.edital
    an = item.analysis

    console.print(Panel(
        f"[bold white]{ed.nome}[/bold white]",
        title=f"📋 Edital SIGProj #{ed.id}",
        subtitle=f"Link: {ed.link_publico}",
        border_style="cyan"
    ))

    # Tabela com Metadados do Edital
    meta_table = Table(show_header=False, box=None)
    meta_table.add_column("Chave", style="dim cyan", width=18)
    meta_table.add_column("Valor", style="white")

    meta_table.add_row("Programa:", ed.programa_nome or "N/A")
    meta_table.add_row("Tipo de Edital:", ed.tipo_edital_nome or "N/A")
    meta_table.add_row("Público Alvo:", ", ".join(ed.publico_alvo) if ed.publico_alvo else "Geral / Alunos")
    meta_table.add_row("Abertura:", ed.data_abertura or "N/A")
    meta_table.add_row("Encerramento:", ed.data_encerramento or "N/A")
    dias = ed.dias_restantes
    dias_str = f"[bold green]{dias} dias restantes[/bold green]" if (dias and dias > 5) else f"[bold red]{dias} dias restantes![/bold red]" if dias is not None else "Encerrado"
    meta_table.add_row("Tempo Restante:", dias_str)
    
    console.print(meta_table)

    if ed.descricao:
        console.print("\n[bold]📝 Descrição Oficial:[/bold]")
        console.print(f"[dim]{ed.descricao}[/dim]\n")

    # Análise de IA
    if an:
        score_color = "green" if an.score >= 80 else ("yellow" if an.score >= 60 else "red")
        ai_box = f"""[bold]Relevância para Computação:[/bold] [{score_color}]{'SIM' if an.relevante else 'NÃO'} (Score: {an.score}/100)[/{score_color}]
[bold]Área:[/bold] [magenta]{an.area}[/magenta]
[bold]Público Alvo p/ Estudantes:[/bold] {'✅ Sim' if an.publico_alvo_estudante else '❌ Não / Servidores'}

[bold]💡 Justificativa da IA:[/bold]
{an.justificativa}

[bold]🏷️ Tags:[/bold] {', '.join(an.tags) if an.tags else 'Nenhuma'}
[bold]📌 Destaques:[/bold] {'; '.join(an.requisitos_destaque) if an.requisitos_destaque else 'Nenhum'}

[dim]Analisado em: {item.analyzed_at or 'N/A'} via {item.model_used or 'N/A'}[/dim]"""

        console.print(Panel(ai_box, title="🧠 Parecer da IA", border_style=score_color))
    else:
        console.print("[yellow]⚠️  Este edital ainda não possui análise por IA salva. Execute 'python main.py fetch' para analisar.[/yellow]")

    # Busca anexos atualizados
    with console.status("Buscando anexos disponíveis no SIGProj..."):
        arquivos = scraper.fetch_edital_files(ed.id)
        if not arquivos:
            arquivos = ed.anexos

    if arquivos:
        console.print("\n[bold]📎 Documentos e Anexos:[/bold]")
        for a in arquivos:
            console.print(f"  • [blue]{a.nome}[/blue] [dim]({a.url})[/dim]")
    console.print()

def cmd_export(args):
    """Exporta os editais relevantes para JSON, CSV ou Markdown."""
    storage = Storage()
    items = storage.get_relevant_editais(min_score=args.min_score)

    output_file = args.output
    fmt = args.format.lower()

    if fmt == "json":
        if not output_file:
            output_file = "editais_relevantes.json"
        data = [item.model_dump() for item in items]
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"[green]✅ Exportado {len(items)} editais para [bold]{output_file}[/bold][/green]")

    elif fmt == "csv":
        if not output_file:
            output_file = "editais_relevantes.csv"
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "score", "area", "nome", "programa", "encerramento", "dias_restantes", "tags", "justificativa", "link"])
            for item in items:
                ed = item.edital
                an = item.analysis
                writer.writerow([
                    ed.id,
                    an.score if an else "",
                    an.area if an else "",
                    ed.nome,
                    ed.programa_nome or "",
                    ed.data_encerramento or "",
                    ed.dias_restantes if ed.dias_restantes is not None else "",
                    ", ".join(an.tags) if an else "",
                    an.justificativa if an else "",
                    ed.link_publico
                ])
        console.print(f"[green]✅ Exportado {len(items)} editais para [bold]{output_file}[/bold][/green]")

    elif fmt == "md":
        if not output_file:
            output_file = "editais_relevantes.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# 🎯 Editais SIGProj Relevantes para Estudantes de Computação\n\n")
            f.write(f"*Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n")
            for item in items:
                ed = item.edital
                an = item.analysis
                f.write(f"## [{ed.nome}]({ed.link_publico})\n")
                if an:
                    f.write(f"- **Score de Relevância:** `{an.score}/100` | **Área:** {an.area}\n")
                    f.write(f"- **Tags:** {', '.join(f'`{t}`' for t in an.tags)}\n")
                    f.write(f"- **Por que é relevante:** {an.justificativa}\n")
                f.write(f"- **Programa:** {ed.programa_nome or 'N/A'}\n")
                f.write(f"- **Prazo final:** {ed.data_encerramento or 'N/A'} ({ed.dias_restantes} dias restantes)\n\n---\n\n")
        console.print(f"[green]✅ Exportado {len(items)} editais para [bold]{output_file}[/bold][/green]")

def cmd_web(args):
    """Inicia o servidor web com o painel interativo."""
    import uvicorn
    console.print(f"\n[bold green]🚀 Iniciando Web Dashboard em http://{args.host}:{args.port}[/bold green]")
    console.print("[dim]Pressione Ctrl+C para encerrar o servidor.[/dim]\n")
    uvicorn.run("web:app", host=args.host, port=args.port, reload=args.reload)

def main():
    parser = argparse.ArgumentParser(
        description="Filtro Inteligente com IA de Editais do SIGProj para Estudantes de Computação"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Baixa editais do SIGProj e classifica com IA")
    p_fetch.add_argument("--limit", type=int, default=None, help="Limite máximo de editais a baixar")
    p_fetch.add_argument("--force", action="store_true", help="Forçar re-análise de todos os editais")

    # list
    p_list = subparsers.add_parser("list", help="Lista editais relevantes salvos no banco local")
    p_list.add_argument("--min-score", type=int, default=settings.MIN_RELEVANCE_SCORE, help="Score mínimo de relevância")
    p_list.add_argument("--area", type=str, default=None, help="Filtrar por área específica")
    p_list.add_argument("--all", action="store_true", help="Exibir todos os editais, inclusive irrelevantes")
    p_list.add_argument("--include-closed", action="store_true", help="Incluir editais já encerrados")
    p_list.add_argument("-l", "--links", action="store_true", help="Exibir coluna com link direto de cada edital")

    # link
    p_link = subparsers.add_parser("link", help="Obtém o link direto do edital ou de seus PDFs")
    p_link.add_argument("id", type=int, help="ID do edital no SIGProj")
    p_link.add_argument("-o", "--open", action="store_true", help="Abrir o link no navegador")
    p_link.add_argument("-u", "--only-url", action="store_true", help="Exibir apenas a URL crua (ideal para scripts/copiar)")
    p_link.add_argument("-p", "--pdf", action="store_true", help="Obter o link do PDF/anexo do edital")

    # show
    p_show = subparsers.add_parser("show", help="Exibe detalhes completos de um edital")
    p_show.add_argument("id", type=int, help="ID do edital no SIGProj")

    # export
    p_export = subparsers.add_parser("export", help="Exporta editais relevantes para arquivo")
    p_export.add_argument("--format", choices=["json", "csv", "md"], default="md", help="Formato de exportação")
    p_export.add_argument("--output", type=str, default=None, help="Caminho do arquivo de saída")
    p_export.add_argument("--min-score", type=int, default=settings.MIN_RELEVANCE_SCORE)

    # web
    p_web = subparsers.add_parser("web", help="Inicia painel web interativo")
    p_web.add_argument("--host", type=str, default="127.0.0.1", help="Host do servidor web")
    p_web.add_argument("--port", type=int, default=8000, help="Porta do servidor web")
    p_web.add_argument("--no-reload", dest="reload", action="store_false", help="Desativar auto-reload para desenvolvimento")
    p_web.set_defaults(reload=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "link":
        cmd_link(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "web":
        cmd_web(args)

if __name__ == "__main__":
    main()
