import json
import logging
from typing import Optional, List, Dict, Any
from config import settings
from models import Edital, AIAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um especialista em oportunidades acadêmicas e de carreira na área de Computação e Tecnologia da Informação.
Sua missão é analisar editais universitários (do sistema SIGProj) e determinar a relevância de cada um para estudantes universitários de Computação (Ciência da Computação, Engenharia de Software, Sistemas de Informação, Engenharia da Computação, Análise e Desenvolvimento de Sistemas, Ciência de Dados, IA).

Critérios de pontuação (Score de 0 a 100):
- 85 a 100 (Alta Relevância): Editais diretamente voltados para TI/Computação (ex: FACOM, DTI, AGETEC, desenvolvimento de software, automação, IA, ciência de dados, maratonas/hackathons, bolsas de desenvolvimento, PIBITI/PIBIC em computação).
- 60 a 84 (Média Relevância): Editais de inovação, empreendedorismo, empresas juniores, saúde digital (ex: PET-Saúde Digital), editais gerais com vagas multidisciplinares para tecnologia/sistemas, ou editais amplos de bolsas com espaço para projetos de TI.
- 30 a 59 (Baixa Relevância): Editais gerais da universidade onde TI tem aplicação muito marginal ou secundária.
- 0 a 29 (Irrelevante): Editais exclusivos de outras áreas (Medicina tradicional, Odontologia, Letras, Artes, Agrárias), editais puramente administrativos de servidores docentes/técnicos (ex: PGD interno sem vaga de estudante), ou revalidação de diplomas (Revalida).

Para cada edital, responda ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "relevante": true ou false (true se score >= 60),
  "score": número inteiro de 0 a 100,
  "area": "Desenvolvimento de Software" | "Inteligência Artificial & Dados" | "Inovação & Hackathons" | "Iniciação Científica & Pesquisa" | "Infraestrutura & Redes" | "Bolsas & Extensão" | "Não Relevante",
  "publico_alvo_estudante": true ou false (se aceita alunos de graduação/pós),
  "justificativa": "Texto explicativo curto e direto (1-3 frases) explicando por que o edital interessa ou não ao estudante de computação",
  "tags": ["tag1", "tag2", "tag3"],
  "requisitos_destaque": ["destaque 1", "destaque 2"]
}
"""

class BaseAIEngine:
    def analyze(self, edital: Edital) -> AIAnalysis:
        raise NotImplementedError

class GeminiAIEngine(BaseAIEngine):
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        from google import genai
        from google.genai import types
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.types = types

    def analyze(self, edital: Edital) -> AIAnalysis:
        prompt = f"""Analise este edital do SIGProj para um estudante de Computação:

ID: {edital.id}
Título: {edital.nome}
Descrição: {edital.descricao or 'Não informada'}
Programa: {edital.programa_nome or 'Não informado'}
Tipo de Edital: {edital.tipo_edital_nome or 'Não informado'}
Público Alvo declarado: {', '.join(edital.publico_alvo) if edital.publico_alvo else 'Geral / Não especificado'}
Data Encerramento: {edital.data_encerramento or 'Não informada'}

Retorne exclusivamente o JSON de acordo com o schema solicitado."""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt],
            config=self.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            )
        )

        data = json.loads(response.text)
        return AIAnalysis(**data)

class OpenAIAIEngine(BaseAIEngine):
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", base_url: Optional[str] = None):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model_name = model_name

    def analyze(self, edital: Edital) -> AIAnalysis:
        prompt = f"""Analise este edital do SIGProj para um estudante de Computação:

ID: {edital.id}
Título: {edital.nome}
Descrição: {edital.descricao or 'Não informada'}
Programa: {edital.programa_nome or 'Não informado'}
Tipo de Edital: {edital.tipo_edital_nome or 'Não informado'}
Público Alvo declarado: {', '.join(edital.publico_alvo) if edital.publico_alvo else 'Geral / Não especificado'}
Data Encerramento: {edital.data_encerramento or 'Não informada'}

Retorne exclusivamente o JSON formatado conforme as instruções."""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return AIAnalysis(**data)

class HeuristicAIEngine(BaseAIEngine):
    """
    Motor heurístico inteligente de fallback quando nenhuma chave de API é fornecida.
    Analisa termos-chave, departamentos e padrões acadêmicos.
    """
    def analyze(self, edital: Edital) -> AIAnalysis:
        texto = f"{edital.nome} {edital.descricao} {edital.programa_nome} {' '.join(edital.publico_alvo)}".lower()

        high_keywords = [
            "computação", "facom", "software", "hackathon", "programação", 
            "inteligência artificial", "ciência de dados", "tecnologia da informação",
            "dti", "agetec", "desenvolvedor", "sistemas de informação", "algoritmo",
            "piviti", "pibiti", "robótica", "saúde digital", "digital"
        ]
        medium_keywords = [
            "inovação", "patente", "empresa júnior", "incubadora", "tecnologia",
            "propriedade intelectual", "pesquisador", "iniciação científica",
            "auxílio financeiro", "empreendedorismo", "laboratórios", "times de impacto"
        ]
        negative_keywords = [
            "revalida", "odontologia", "medicina", "veterinária", "enfermagem",
            "faalc", "inisa", "letras", "arte", "música", "dança", "pgd",
            "servidores", "docentes", "técnico-administrativo"
        ]

        score = 20
        tags = []
        area = "Não Relevante"
        justificativa_itens = []

        # Detecção de alta relevância
        for kw in high_keywords:
            if kw in texto:
                score += 50
                tags.append(kw.title())
                justificativa_itens.append(f"menção a '{kw}'")

        # Detecção de média relevância
        for kw in medium_keywords:
            if kw in texto:
                score += 20
                tags.append(kw.title())
                justificativa_itens.append(f"relação com '{kw}'")

        # Boost especial para Hackathons e FACOM
        if "hackathon" in texto:
            score = max(score, 90)
            tags.append("Hackathon")
        if "facom" in texto:
            score = max(score, 88)
            tags.append("FACOM")

        # Penalidades para editais explicitamente de outras áreas ou PGD de servidores
        for kw in negative_keywords:
            if kw in texto and not any(h in texto for h in ["saúde digital", "facom", "hackathon", "tecnologia"]):
                score -= 30

        # Normalização do score
        score = max(5, min(98, score))
        relevante = score >= settings.MIN_RELEVANCE_SCORE

        if "hackathon" in texto:
            area = "Inovação & Hackathons"
        elif any(k in texto for k in ["inteligência artificial", "ciência de dados", "dados"]):
            area = "Inteligência Artificial & Dados"
        elif any(k in texto for k in ["facom", "software", "programação", "desenvolvedor"]):
            area = "Desenvolvimento de Software"
        elif any(k in texto for k in ["pibiti", "piviti", "patente", "pesquisa"]):
            area = "Iniciação Científica & Pesquisa"
        elif any(k in texto for k in ["empresa júnior", "inovação", "empreendedorismo"]):
            area = "Inovação & Hackathons"
        elif relevante:
            area = "Bolsas & Extensão"

        if relevante:
            just = f"[Classificador Heurístico] Edital possui forte potencial para alunos de Computação devido a: {', '.join(justificativa_itens[:3]) or 'conteúdo técnico'}."
        else:
            just = "[Classificador Heurístico] Edital focado em outras áreas ou procedimentos administrativos gerais, com baixa aderência para computação."

        return AIAnalysis(
            relevante=relevante,
            score=score,
            area=area,
            publico_alvo_estudante=True if "aluno" in texto or not ("servidor" in texto or "docente" in texto) else False,
            justificativa=just,
            tags=list(set(tags))[:5],
            requisitos_destaque=["Consulte o anexo do edital para cronograma detalhado"]
        )

def get_ai_engine() -> tuple[BaseAIEngine, str]:
    """
    Retorna o motor de IA apropriado de acordo com a configuração e disponibilidade de chaves.
    """
    provider = settings.AI_PROVIDER

    if provider == "gemini" and settings.GEMINI_API_KEY:
        logger.info(f"Usando Google Gemini ({settings.GEMINI_MODEL})")
        return GeminiAIEngine(settings.GEMINI_API_KEY, settings.GEMINI_MODEL), f"gemini:{settings.GEMINI_MODEL}"

    if provider in ["openai", "groq", "ollama"] and (settings.OPENAI_API_KEY or settings.OPENAI_BASE_URL):
        logger.info(f"Usando OpenAI/Compatível ({settings.OPENAI_MODEL})")
        return OpenAIAIEngine(
            api_key=settings.OPENAI_API_KEY or "no-key",
            model_name=settings.OPENAI_MODEL,
            base_url=settings.OPENAI_BASE_URL or None
        ), f"openai:{settings.OPENAI_MODEL}"

    logger.info("Chave de API não configurada; utilizando motor Heurístico inteligente de fallback.")
    return HeuristicAIEngine(), "heuristic:rule-based-v1"
