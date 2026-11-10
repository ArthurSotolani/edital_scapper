from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

import json
from config import settings

class EditalArquivo(BaseModel):
    id: Optional[int] = None
    nome: str
    tipo: Optional[str] = None
    url: Optional[str] = None

class Edital(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = ""
    data_abertura: Optional[str] = None
    data_encerramento: Optional[str] = None
    ativo: bool = True
    programa_id: Optional[int] = None
    programa_nome: Optional[str] = None
    tipo_edital_id: Optional[int] = None
    tipo_edital_nome: Optional[str] = None
    publico_alvo: List[str] = Field(default_factory=list)
    anexos: List[EditalArquivo] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    @property
    def link_publico(self) -> str:
        base = settings.SIGPROJ_BASE_URL.rstrip("/")
        return f"{base}/publico/editais/{self.id}"

    def get_all_anexos(self) -> List[EditalArquivo]:
        """Retorna anexos existentes ou extrai da estrutura de dados do edital."""
        if self.anexos:
            return self.anexos

        resultado: List[EditalArquivo] = []
        dados = self.raw_data.get("dados")
        if isinstance(dados, str):
            try:
                dados = json.loads(dados)
                if isinstance(dados, str):
                    dados = json.loads(dados)
            except Exception:
                dados = None

        if isinstance(dados, dict):
            grupos = dados.get("anexos") or []
            for g in grupos:
                if isinstance(g, dict):
                    for a in g.get("anexo") or []:
                        if isinstance(a, dict):
                            resultado.append(EditalArquivo(
                                nome=a.get("name", "Documento"),
                                tipo=a.get("type", "application/pdf"),
                                url=a.get("content")
                            ))
        return resultado

    @property
    def dias_restantes(self) -> Optional[int]:
        if not self.data_encerramento:
            return None
        try:
            # Handle ISO string like "2026-11-16T03:59:00Z"
            clean_date = self.data_encerramento.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_date)
            # compare to now in utc
            now = datetime.now(dt.tzinfo)
            diff = (dt - now).days
            return max(0, diff)
        except Exception:
            return None

class AIAnalysis(BaseModel):
    relevante: bool = Field(
        ...,
        description="Se o edital é relevante para um estudante de Computação/TI (Engenharia de Software, Ciência da Computação, Sistemas de Informação, etc.)"
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Grau de relevância de 0 a 100 para estudantes de Computação"
    )
    area: str = Field(
        ...,
        description="Área principal: ex. 'Desenvolvimento de Software', 'Inteligência Artificial & Dados', 'Inovação & Hackathons', 'Iniciação Científica & Pesquisa', 'Infraestrutura & Redes', 'Bolsa de Extensão', ou 'Não Relevante'"
    )
    publico_alvo_estudante: bool = Field(
        ...,
        description="Se o edital aceita estudantes de graduação ou pós-graduação como bolsistas ou participantes"
    )
    justificativa: str = Field(
        ...,
        description="Explicação concisa e objetiva de por que o edital é ou não é relevante para o estudante"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Palavras-chave e tags relevantes (ex: Python, Hackathon, FACOM, Web, Bolsa R$ 700)"
    )
    requisitos_destaque: List[str] = Field(
        default_factory=list,
        description="Principais requisitos ou oportunidades para o aluno"
    )

class EditalFull(BaseModel):
    edital: Edital
    analysis: Optional[AIAnalysis] = None
    analyzed_at: Optional[str] = None
    model_used: Optional[str] = None
