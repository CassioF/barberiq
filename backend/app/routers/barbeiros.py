"""CRUD de barbeiros (admin escreve; qualquer usuário logado lê) + disponibilidade semanal."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.deps import usuario_atual
from app.routers.usuarios_base import criar_router

router = criar_router("/barbeiros", "Barbeiros", models.TipoUsuario.barbeiro, "Barbeiro", leitura=usuario_atual)

disp = APIRouter(prefix="/barbeiros", tags=["Barbeiros"])


def _barbeiro_ou_404(db: Session, barbeiro_id: int) -> models.Usuario:
    b = crud.obter_usuario(db, barbeiro_id, models.TipoUsuario.barbeiro)
    if not b:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")
    return b


@disp.get("/{barbeiro_id}/disponibilidade", response_model=list[schemas.DisponibilidadeOut],
          summary="Janelas semanais de trabalho do barbeiro")
def ver_disponibilidade(barbeiro_id: int, db: Session = Depends(get_db),
                        _: models.Usuario = Depends(usuario_atual)):
    _barbeiro_ou_404(db, barbeiro_id)
    return crud.listar_disponibilidade(db, barbeiro_id)


@disp.put("/{barbeiro_id}/disponibilidade", response_model=list[schemas.DisponibilidadeOut],
          summary="Substitui as janelas semanais (admin ou o próprio barbeiro)")
def definir_disponibilidade(barbeiro_id: int, janelas: list[schemas.DisponibilidadeIn],
                            db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    _barbeiro_ou_404(db, barbeiro_id)
    if usuario.tipo != models.TipoUsuario.admin and usuario.id != barbeiro_id:
        raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")
    por_dia: dict[int, list] = {}
    for j in janelas:
        por_dia.setdefault(j.dia_semana, []).append(j)
    for lista in por_dia.values():
        lista.sort(key=lambda x: x.hora_inicio)
        for a, b in zip(lista, lista[1:]):
            if b.hora_inicio < a.hora_fim:
                raise HTTPException(status_code=422, detail="Há janelas sobrepostas no mesmo dia.")
    return crud.substituir_disponibilidade(db, barbeiro_id, janelas)
