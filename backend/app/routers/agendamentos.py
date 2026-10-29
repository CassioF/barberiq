"""
Agendamentos.
- Cliente: vê e cancela os próprios; cria para si.
- Barbeiro: vê a própria agenda e marca concluído / faltou.
- Admin: vê tudo e pode agendar em nome de um cliente.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload

from app import agenda, crud, models, notificacoes, schemas, tempo
from app.database import get_db
from app.deps import usuario_atual

router = APIRouter(prefix="/agendamentos", tags=["Agendamentos"])
SA = models.StatusAgendamento
TU = models.TipoUsuario


def _mostrar_risco(u: models.Usuario) -> bool:
    return u.tipo in (TU.admin, TU.barbeiro)


def _carregar(db: Session, ag_id: int) -> models.Agendamento:
    ag = db.get(models.Agendamento, ag_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    return ag


def _pode_ver(u: models.Usuario, ag: models.Agendamento) -> bool:
    return (
        u.tipo == TU.admin
        or (u.tipo == TU.cliente and ag.cliente_id == u.id)
        or (u.tipo == TU.barbeiro and ag.barbeiro_id == u.id)
    )


@router.get("/horarios-livres", response_model=schemas.HorariosLivresOut,
            summary="Horários livres de um barbeiro para um serviço em um dia")
def horarios_livres(
    barbeiro_id: int, servico_id: int, data: date,
    db: Session = Depends(get_db), _: models.Usuario = Depends(usuario_atual),
):
    servico = crud.obter_servico(db, servico_id)
    if not servico or not servico.ativo:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    if not crud.obter_usuario(db, barbeiro_id, TU.barbeiro):
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")
    return {"data": data.isoformat(), "horarios": agenda.horarios_livres(db, barbeiro_id, servico, data)}


@router.post("", response_model=schemas.AgendamentoOut, status_code=201, summary="Criar agendamento")
def criar(dados: schemas.AgendamentoCreate, db: Session = Depends(get_db),
          usuario: models.Usuario = Depends(usuario_atual)):
    if usuario.tipo == TU.cliente:
        cliente = usuario
    elif usuario.tipo == TU.admin:
        if not dados.cliente_id:
            raise HTTPException(status_code=422, detail="Informe o cliente_id.")
        cliente = crud.obter_usuario(db, dados.cliente_id, TU.cliente)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    else:
        raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")
    ag = agenda.criar_agendamento(db, cliente, dados.barbeiro_id, dados.servico_id, dados.data_hora)
    return agenda.para_saida(ag, _mostrar_risco(usuario))


@router.get("", response_model=list[schemas.AgendamentoOut], summary="Listar agendamentos (filtrados pelo perfil)")
def listar(
    response: Response,
    data_de: Optional[date] = None, data_ate: Optional[date] = None,
    status: Optional[SA] = None, barbeiro_id: Optional[int] = None, cliente_id: Optional[int] = None,
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual),
):
    q = db.query(models.Agendamento).options(
        joinedload(models.Agendamento.cliente), joinedload(models.Agendamento.barbeiro),
        joinedload(models.Agendamento.servico), joinedload(models.Agendamento.previsao),
    )
    if usuario.tipo == TU.cliente:
        q = q.filter(models.Agendamento.cliente_id == usuario.id)
    elif usuario.tipo == TU.barbeiro:
        q = q.filter(models.Agendamento.barbeiro_id == usuario.id)
    else:
        if barbeiro_id:
            q = q.filter(models.Agendamento.barbeiro_id == barbeiro_id)
        if cliente_id:
            q = q.filter(models.Agendamento.cliente_id == cliente_id)
    if data_de:
        q = q.filter(models.Agendamento.data_hora >= datetime.combine(data_de, datetime.min.time()))
    if data_ate:
        q = q.filter(models.Agendamento.data_hora < datetime.combine(data_ate + timedelta(days=1), datetime.min.time()))
    if status:
        q = q.filter(models.Agendamento.status == status)
    response.headers["X-Total-Count"] = str(q.count())
    ags = q.order_by(models.Agendamento.data_hora).offset(skip).limit(limit).all()
    return [agenda.para_saida(a, _mostrar_risco(usuario)) for a in ags]


@router.get("/{agendamento_id}", response_model=schemas.AgendamentoOut, summary="Obter agendamento")
def obter(agendamento_id: int, db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    ag = _carregar(db, agendamento_id)
    if not _pode_ver(usuario, ag):
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    return agenda.para_saida(ag, _mostrar_risco(usuario))


@router.patch("/{agendamento_id}/cancelar", response_model=schemas.AgendamentoOut, summary="Cancelar agendamento")
def cancelar(agendamento_id: int, db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    ag = _carregar(db, agendamento_id)
    if not _pode_ver(usuario, ag):
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    if ag.status != SA.confirmado:
        raise HTTPException(status_code=409, detail="Só é possível cancelar agendamentos confirmados.")
    if ag.data_hora <= tempo.agora():
        raise HTTPException(status_code=409, detail="Este horário já passou e não pode ser cancelado.")
    ag.status = SA.cancelado
    db.commit()
    db.refresh(ag)
    notificacoes.notificar_cancelamento(db, ag)
    return agenda.para_saida(ag, _mostrar_risco(usuario))


@router.patch("/{agendamento_id}/status", response_model=schemas.AgendamentoOut,
              summary="Marcar atendimento como concluído / faltou (barbeiro ou admin)")
def mudar_status(agendamento_id: int, dados: schemas.AgendamentoStatusIn, db: Session = Depends(get_db),
                 usuario: models.Usuario = Depends(usuario_atual)):
    if usuario.tipo == TU.cliente:
        raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")
    ag = _carregar(db, agendamento_id)
    if not _pode_ver(usuario, ag):
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    if dados.status == SA.confirmado:
        raise HTTPException(status_code=422, detail="Use concluido, faltou ou cancelado.")
    if ag.status == SA.cancelado:
        raise HTTPException(status_code=409, detail="Agendamento cancelado não pode ser alterado.")
    if dados.status in (SA.concluido, SA.faltou) and ag.data_hora > tempo.agora():
        raise HTTPException(status_code=409, detail="O atendimento ainda não aconteceu.")
    era_cancelado = dados.status == SA.cancelado and ag.status == SA.confirmado
    ag.status = dados.status
    db.commit()
    db.refresh(ag)
    if era_cancelado:
        notificacoes.notificar_cancelamento(db, ag)
    return agenda.para_saida(ag, True)
