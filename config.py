import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    
    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # OpenAI / Compatíveis (Groq, Ollama, etc.)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    
    # Parâmetros de filtragem
    MIN_RELEVANCE_SCORE: int = int(os.getenv("MIN_RELEVANCE_SCORE", "60"))
    
    # SIGProj
    SIGPROJ_BASE_URL: str = os.getenv("SIGPROJ_BASE_URL", "https://sigproj.ufms.br").rstrip("/")
    
    # Banco de Dados SQLite
    DB_PATH: Path = BASE_DIR / "editais.db"

settings = Settings()
