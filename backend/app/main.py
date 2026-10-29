"""
Ponto de entrada da API — AI Barbershop (BarberIQ).

Rodar:  uvicorn app.main:app --reload
Docs :  http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app import models, notificacoes  # noqa: F401  (models registra as tabelas)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import agendamentos, auth, barbeiros, clientes, ia, relatorios, servicos
from app.routers import notificacoes as rota_notificacoes

log = logging.getLogger("barberiq")


def _lembretes_uma_vez():
    with SessionLocal() as db:
        n = notificacoes.disparar_lembretes(db)
        if n:
            log.info("Lembretes enviados: %s", n)


async def _loop_lembretes():
    while True:
        await asyncio.sleep(settings.LEMBRETES_INTERVALO_MIN * 60)
        try:
            await run_in_threadpool(_lembretes_uma_vez)
        except Exception:
            log.exception("Erro no disparo automático de lembretes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    tarefa = asyncio.create_task(_loop_lembretes()) if settings.LEMBRETES_INTERVALO_MIN > 0 else None
    yield
    if tarefa:
        tarefa.cancel()


app = FastAPI(
    title="AI Barbershop — API",
    description="Agendamento inteligente para barbearias, com previsão de no-show (IA).",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

for r in (auth.router, clientes.router, barbeiros.router, barbeiros.disp, servicos.router,
          agendamentos.router, ia.router, rota_notificacoes.router, relatorios.router):
    app.include_router(r)


@app.get("/", tags=["Status"], summary="Verifica se a API está no ar")
def raiz():
    return {"status": "ok", "servico": "AI Barbershop - API"}
