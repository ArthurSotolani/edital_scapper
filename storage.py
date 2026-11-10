import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from config import settings
from models import Edital, AIAnalysis, EditalFull, EditalArquivo

class Storage:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS editais (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                descricao TEXT,
                data_abertura TEXT,
                data_encerramento TEXT,
                ativo INTEGER DEFAULT 1,
                programa_id INTEGER,
                programa_nome TEXT,
                tipo_edital_id INTEGER,
                tipo_edital_nome TEXT,
                publico_alvo_json TEXT,
                raw_json TEXT,
                updated_at TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analyses (
                edital_id INTEGER PRIMARY KEY,
                relevante INTEGER NOT NULL,
                score INTEGER NOT NULL,
                area TEXT,
                publico_alvo_estudante INTEGER,
                justificativa TEXT,
                tags_json TEXT,
                requisitos_json TEXT,
                model_used TEXT,
                analyzed_at TEXT,
                FOREIGN KEY (edital_id) REFERENCES editais(id)
            )
            """)
            conn.commit()

    def save_edital(self, edital: Edital):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO editais (
                id, nome, descricao, data_abertura, data_encerramento, ativo,
                programa_id, programa_nome, tipo_edital_id, tipo_edital_nome,
                publico_alvo_json, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nome=excluded.nome,
                descricao=excluded.descricao,
                data_abertura=excluded.data_abertura,
                data_encerramento=excluded.data_encerramento,
                ativo=excluded.ativo,
                programa_nome=excluded.programa_nome,
                tipo_edital_nome=excluded.tipo_edital_nome,
                publico_alvo_json=excluded.publico_alvo_json,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """, (
                edital.id,
                edital.nome,
                edital.descricao,
                edital.data_abertura,
                edital.data_encerramento,
                1 if edital.ativo else 0,
                edital.programa_id,
                edital.programa_nome,
                edital.tipo_edital_id,
                edital.tipo_edital_nome,
                json.dumps(edital.publico_alvo, ensure_ascii=False),
                json.dumps(edital.raw_data, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            conn.commit()

    def save_analysis(self, edital_id: int, analysis: AIAnalysis, model_used: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO ai_analyses (
                edital_id, relevante, score, area, publico_alvo_estudante,
                justificativa, tags_json, requisitos_json, model_used, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(edital_id) DO UPDATE SET
                relevante=excluded.relevante,
                score=excluded.score,
                area=excluded.area,
                publico_alvo_estudante=excluded.publico_alvo_estudante,
                justificativa=excluded.justificativa,
                tags_json=excluded.tags_json,
                requisitos_json=excluded.requisitos_json,
                model_used=excluded.model_used,
                analyzed_at=excluded.analyzed_at
            """, (
                edital_id,
                1 if analysis.relevante else 0,
                analysis.score,
                analysis.area,
                1 if analysis.publico_alvo_estudante else 0,
                analysis.justificativa,
                json.dumps(analysis.tags, ensure_ascii=False),
                json.dumps(analysis.requisitos_destaque, ensure_ascii=False),
                model_used,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_analysis(self, edital_id: int) -> Optional[Tuple[AIAnalysis, str, str]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_analyses WHERE edital_id = ?", (edital_id,))
            row = cursor.fetchone()
            if not row:
                return None
            analysis = AIAnalysis(
                relevante=bool(row["relevante"]),
                score=row["score"],
                area=row["area"] or "",
                publico_alvo_estudante=bool(row["publico_alvo_estudante"]),
                justificativa=row["justificativa"] or "",
                tags=json.loads(row["tags_json"] or "[]"),
                requisitos_destaque=json.loads(row["requisitos_json"] or "[]")
            )
            return analysis, row["model_used"], row["analyzed_at"]

    def _row_to_edital_full(self, row: sqlite3.Row) -> EditalFull:
        publico_alvo = json.loads(row["publico_alvo_json"] or "[]")
        raw_data = json.loads(row["raw_json"] or "{}")
        edital = Edital(
            id=row["id"],
            nome=row["nome"],
            descricao=row["descricao"] or "",
            data_abertura=row["data_abertura"],
            data_encerramento=row["data_encerramento"],
            ativo=bool(row["ativo"]),
            programa_id=row["programa_id"],
            programa_nome=row["programa_nome"],
            tipo_edital_id=row["tipo_edital_id"],
            tipo_edital_nome=row["tipo_edital_nome"],
            publico_alvo=publico_alvo,
            raw_data=raw_data
        )
        edital.anexos = edital.get_all_anexos()

        analysis = None
        analyzed_at = None
        model_used = None

        if row["ai_edital_id"] is not None:
            analysis = AIAnalysis(
                relevante=bool(row["relevante"]),
                score=row["score"],
                area=row["area"] or "",
                publico_alvo_estudante=bool(row["publico_alvo_estudante"]),
                justificativa=row["justificativa"] or "",
                tags=json.loads(row["tags_json"] or "[]"),
                requisitos_destaque=json.loads(row["requisitos_json"] or "[]")
            )
            analyzed_at = row["analyzed_at"]
            model_used = row["model_used"]

        return EditalFull(
            edital=edital,
            analysis=analysis,
            analyzed_at=analyzed_at,
            model_used=model_used
        )

    def get_edital_full(self, edital_id: int) -> Optional[EditalFull]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT e.*, 
                   a.edital_id as ai_edital_id, a.relevante, a.score, a.area,
                   a.publico_alvo_estudante, a.justificativa, a.tags_json,
                   a.requisitos_json, a.model_used, a.analyzed_at
            FROM editais e
            LEFT JOIN ai_analyses a ON e.id = a.edital_id
            WHERE e.id = ?
            """, (edital_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_edital_full(row)

    def get_relevant_editais(self, min_score: Optional[int] = None, area: Optional[str] = None, only_active: bool = True) -> List[EditalFull]:
        min_score = min_score if min_score is not None else settings.MIN_RELEVANCE_SCORE
        query = """
        SELECT e.*, 
               a.edital_id as ai_edital_id, a.relevante, a.score, a.area,
               a.publico_alvo_estudante, a.justificativa, a.tags_json,
               a.requisitos_json, a.model_used, a.analyzed_at
        FROM editais e
        INNER JOIN ai_analyses a ON e.id = a.edital_id
        WHERE a.score >= ?
        """
        params = [min_score]
        if only_active:
            query += " AND e.ativo = 1"
        if area:
            query += " AND a.area LIKE ?"
            params.append(f"%{area}%")

        query += " ORDER BY a.score DESC, e.data_encerramento ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_edital_full(r) for r in cursor.fetchall()]

    def get_all_editais_full(self, only_active: bool = False) -> List[EditalFull]:
        query = """
        SELECT e.*, 
               a.edital_id as ai_edital_id, a.relevante, a.score, a.area,
               a.publico_alvo_estudante, a.justificativa, a.tags_json,
               a.requisitos_json, a.model_used, a.analyzed_at
        FROM editais e
        LEFT JOIN ai_analyses a ON e.id = a.edital_id
        """
        params = []
        if only_active:
            query += " WHERE e.ativo = 1"
        query += " ORDER BY COALESCE(a.score, 0) DESC, e.data_encerramento ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_edital_full(r) for r in cursor.fetchall()]

    def get_unanalyzed_editais(self) -> List[Edital]:
        query = """
        SELECT e.*
        FROM editais e
        LEFT JOIN ai_analyses a ON e.id = a.edital_id
        WHERE a.edital_id IS NULL AND e.ativo = 1
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            items = []
            for row in cursor.fetchall():
                items.append(Edital(
                    id=row["id"],
                    nome=row["nome"],
                    descricao=row["descricao"] or "",
                    data_abertura=row["data_abertura"],
                    data_encerramento=row["data_encerramento"],
                    ativo=bool(row["ativo"]),
                    programa_id=row["programa_id"],
                    programa_nome=row["programa_nome"],
                    tipo_edital_id=row["tipo_edital_id"],
                    tipo_edital_nome=row["tipo_edital_nome"],
                    publico_alvo=json.loads(row["publico_alvo_json"] or "[]"),
                    raw_data=json.loads(row["raw_json"] or "{}")
                ))
            return items
