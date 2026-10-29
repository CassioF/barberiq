"""Painel administrativo: faturamento, ocupação, no-show."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, tempo
from app.config import settings
from app.database import get_db
from app.deps import somente_admin
from app.ia.noshow import nivel

router = APIRouter(prefix="/relatorios", tags=["Relatórios (admin)"], dependencies=[Depends(somente_admin)])
SA = models.StatusAgendamento


def _minutos(ini, fim) -> int:
    return (fim.hour * 60 + fim.minute) - (ini.hour * 60 + ini.minute)


@router.get("/resumo", summary="Indicadores do período (padrão: últimos 30 dias)")
def resumo(data_de: Optional[date] = None, data_ate: Optional[date] = None, db: Session = Depends(get_db)):
    hoje = tempo.agora().date()
    data_ate = data_ate or hoje
    data_de = data_de or (data_ate - timedelta(days=29))
    if data_de > data_ate:
        raise HTTPException(status_code=422, detail="data_de deve ser anterior a data_ate.")
    if (data_ate - data_de).days > 366:
        raise HTTPException(status_code=422, detail="Período máximo de 366 dias.")

    ini = datetime.combine(data_de, datetime.min.time())
    fim = datetime.combine(data_ate + timedelta(days=1), datetime.min.time())
    ags = (
        db.query(models.Agendamento)
        .options(joinedload(models.Agendamento.servico), joinedload(models.Agendamento.barbeiro),
                 joinedload(models.Agendamento.previsao))
        .filter(models.Agendamento.data_hora >= ini, models.Agendamento.data_hora < fim)
        .all()
    )

    por_status = defaultdict(int)
    fat_dia: dict[str, float] = defaultdict(float)
    fat_servico: dict[str, dict] = {}
    fat_barbeiro: dict[int, dict] = {}
    min_ocupados: dict[int, int] = defaultdict(int)
    faturamento = 0.0
    for a in ags:
        por_status[a.status.value] += 1
        if a.status in (SA.confirmado, SA.concluido, SA.faltou):
            min_ocupados[a.barbeiro_id] += a.servico.duracao_min
        if a.status == SA.concluido:
            v = float(a.servico.preco)
            faturamento += v
            fat_dia[a.data_hora.date().isoformat()] += v
            s = fat_servico.setdefault(a.servico.nome, {"servico": a.servico.nome, "atendimentos": 0, "faturamento": 0.0})
            s["atendimentos"] += 1
            s["faturamento"] += v
            b = fat_barbeiro.setdefault(a.barbeiro_id, {"barbeiro": a.barbeiro.nome, "atendimentos": 0, "faturamento": 0.0})
            b["atendimentos"] += 1
            b["faturamento"] += v

    # capacidade = soma das janelas de trabalho em cada dia do período
    barbeiros = db.query(models.Usuario).filter(
        models.Usuario.tipo == models.TipoUsuario.barbeiro, models.Usuario.ativo.is_(True)).all()
    janelas = db.query(models.DisponibilidadeBarbeiro).all()
    min_dia_semana: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for j in janelas:
        min_dia_semana[j.barbeiro_id][j.dia_semana] += _minutos(j.hora_inicio, j.hora_fim)
    ocupacao = []
    cap_total = ocup_total = 0
    for b in barbeiros:
        cap = sum(min_dia_semana[b.id][(data_de + timedelta(days=i)).weekday()]
                  for i in range((data_ate - data_de).days + 1))
        oc = min_ocupados.get(b.id, 0)
        cap_total += cap
        ocup_total += oc
        ocupacao.append({"barbeiro": b.nome, "minutos_disponiveis": cap, "minutos_ocupados": oc,
                         "taxa": round(min(oc / cap, 1.0), 4) if cap else 0.0})

    realizados = por_status[SA.concluido.value] + por_status[SA.faltou.value]
    futuros_alto = sum(
        1 for a in ags
        if a.status == SA.confirmado and a.data_hora > tempo.agora() and a.previsao
        and nivel(float(a.previsao.risco), settings.LIMITE_ALTO_RISCO) == "alto"
    )
    return {
        "periodo": {"de": data_de.isoformat(), "ate": data_ate.isoformat()},
        "faturamento_total": round(faturamento, 2),
        "ticket_medio": round(faturamento / por_status[SA.concluido.value], 2) if por_status[SA.concluido.value] else 0.0,
        "agendamentos_total": len(ags),
        "por_status": {s.value: por_status[s.value] for s in SA},
        "taxa_noshow": round(por_status[SA.faltou.value] / realizados, 4) if realizados else 0.0,
        "taxa_cancelamento": round(por_status[SA.cancelado.value] / len(ags), 4) if ags else 0.0,
        "ocupacao_geral": round(min(ocup_total / cap_total, 1.0), 4) if cap_total else 0.0,
        "ocupacao_por_barbeiro": ocupacao,
        "faturamento_por_dia": [{"data": d, "valor": round(v, 2)} for d, v in sorted(fat_dia.items())],
        "faturamento_por_servico": sorted(
            ({**v, "faturamento": round(v["faturamento"], 2)} for v in fat_servico.values()),
            key=lambda x: -x["faturamento"]),
        "faturamento_por_barbeiro": sorted(
            ({**v, "faturamento": round(v["faturamento"], 2)} for v in fat_barbeiro.values()),
            key=lambda x: -x["faturamento"]),
        "futuros_alto_risco": futuros_alto,
    }
