"""Módulo de IA — previsão de no-show (demonstração em tempo real + métricas do modelo)."""
from fastapi import APIRouter, Depends

from app import schemas
from app.config import settings
from app.deps import admin_ou_barbeiro, somente_admin
from app.ia import noshow

router = APIRouter(prefix="/ia/noshow", tags=["IA — No-show"])


@router.get("/metricas", dependencies=[Depends(admin_ou_barbeiro)], summary="Métricas do modelo treinado")
def metricas():
    return {**noshow.metricas(), "limite_alto_risco": settings.LIMITE_ALTO_RISCO}


@router.post("/prever", response_model=schemas.PrevisaoOut, dependencies=[Depends(admin_ou_barbeiro)],
             summary="Simula o risco de falta para variáveis informadas")
def prever(dados: schemas.PrevisaoIn):
    r = noshow.prever(dados.taxa_faltas, dados.dia_semana, dados.antecedencia_horas)
    return {"risco": round(r, 4), "nivel": noshow.nivel(r, settings.LIMITE_ALTO_RISCO)}


@router.post("/treinar", dependencies=[Depends(somente_admin)], summary="Retreina o modelo (dados simulados)")
def treinar():
    return noshow.treinar()
