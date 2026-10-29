"""Relógio da aplicação (fuso configurável). Datas do banco são 'naive' no horário local."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings


def agora() -> datetime:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).replace(tzinfo=None, microsecond=0)
