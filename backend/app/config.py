"""Configurações da aplicação (lidas de variáveis de ambiente / arquivo .env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://postgres:senha123@localhost:5432/barberiq"
    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ACCESS_TOKEN_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Regex opcional de origens extras (ex.: previews do Vercel: https://barberiq.*\.vercel\.app)
    CORS_ORIGIN_REGEX: str = ""
    AUTO_CREATE_TABLES: bool = True
    # Popula dados de demonstração ao iniciar, se o banco ainda não tiver usuários
    # (útil no Render free, que não tem Shell para rodar "python -m app.seed")
    SEED_DEMO: bool = False
    TIMEZONE: str = "America/Sao_Paulo"
    # Intervalo (min) do disparo automático de lembretes; 0 desliga
    LEMBRETES_INTERVALO_MIN: int = 15
    # Passo (min) entre horários oferecidos na agenda
    PASSO_AGENDA_MIN: int = 30
    # Risco a partir do qual o agendamento é tratado como "alto risco"
    LIMITE_ALTO_RISCO: float = 0.5
    # Chatbot com IA (Anthropic). Sem chave, o front usa o modo guiado (botões), sem custo.
    ANTHROPIC_API_KEY: str = ""
    CHAT_MODEL: str = "claude-haiku-5-5"


settings = Settings()
