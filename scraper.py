import json
import logging
from typing import List, Optional, Dict, Any
import requests
from config import settings
from models import Edital, EditalArquivo

logger = logging.getLogger(__name__)

class SIGProjScraper:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.SIGPROJ_BASE_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })

    def fetch_active_editais(self, max_items: Optional[int] = None, page_size: int = 50) -> List[Edital]:
        """
        Busca todos os editais vigentes e ativos no SIGProj.
        Utiliza a API pública REST do SIGProj com paginação automática.
        """
        editais: List[Edital] = []
        page = 0

        while True:
            params = {
                "ativo.equals": "true",
                "rascunho.equals": "false",
                "isVigente.equals": "true",
                "page": page,
                "size": page_size,
                "sort": "dataEncerramento,asc"
            }
            url = f"{self.base_url}/api/editais"
            try:
                resp = self.session.get(url, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Erro ao buscar página {page} de editais: {e}")
                break

            if not data or not isinstance(data, list):
                break

            for item in data:
                edital = self._parse_edital(item)
                editais.append(edital)
                if max_items and len(editais) >= max_items:
                    return editais

            # Se vieram menos itens que o tamanho da página, acabou
            if len(data) < page_size:
                break

            page += 1

        return editais

    def fetch_edital_files(self, edital_id: int) -> List[EditalArquivo]:
        """
        Busca os anexos públicos de um edital específico.
        """
        url = f"{self.base_url}/api/editais-publicos/{edital_id}/arquivos"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    arquivos = []
                    for arq in data:
                        arquivos.append(EditalArquivo(
                            id=arq.get("id"),
                            nome=arq.get("nome", ""),
                            tipo=arq.get("tipo"),
                            url=f"{self.base_url}/api/arquivos/{arq.get('id')}/download"
                        ))
                    return arquivos
        except Exception as e:
            logger.debug(f"Não foi possível obter arquivos para o edital {edital_id}: {e}")
        return []

    def _parse_edital(self, item: Dict[str, Any]) -> Edital:
        configuracoes = item.get("configuracoes")
        publico_alvo = []
        if isinstance(configuracoes, str):
            try:
                configuracoes = json.loads(configuracoes)
            except Exception:
                configuracoes = {}
        if isinstance(configuracoes, dict):
            publico_alvo = configuracoes.get("publico_alvo") or []

        # Tenta extrair anexos do campo 'dados' caso existam
        anexos: List[EditalArquivo] = []
        raw_dados = item.get("dados")
        if isinstance(raw_dados, str):
            try:
                dados_dict = json.loads(raw_dados)
                if isinstance(dados_dict, dict):
                    anexos_raw = dados_dict.get("anexos") or []
                    for grupo in anexos_raw:
                        if isinstance(grupo, dict):
                            for anexo_info in grupo.get("anexo", []):
                                if isinstance(anexo_info, dict):
                                    anexos.append(EditalArquivo(
                                        id=0,
                                        nome=anexo_info.get("name", "Documento"),
                                        tipo=anexo_info.get("type"),
                                        url=anexo_info.get("content")
                                    ))
            except Exception:
                pass

        return Edital(
            id=item["id"],
            nome=item.get("nome", "").strip(),
            descricao=item.get("descricao", "").strip() if item.get("descricao") else "",
            data_abertura=item.get("dataAbertura"),
            data_encerramento=item.get("dataEncerramento"),
            ativo=bool(item.get("ativo", True)),
            programa_id=item.get("programaId"),
            programa_nome=item.get("programaNome"),
            tipo_edital_id=item.get("tipoEditalId"),
            tipo_edital_nome=item.get("tipoEditalNome"),
            publico_alvo=publico_alvo if isinstance(publico_alvo, list) else [],
            anexos=anexos,
            raw_data=item
        )
