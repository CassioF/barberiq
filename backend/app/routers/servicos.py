"""Catálogo de serviços (corte, barba, combo...). Leitura pública; escrita só admin."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.deps import somente_admin

router = APIRouter(prefix="/servicos", tags=["Serviços"])


@router.get("", response_model=list[schemas.ServicoOut], summary="Listar serviços ativos")
def listar(todos: bool = False, db: Session = Depends(get_db)):
    return crud.listar_servicos(db, somente_ativos=not todos)


@router.post("", response_model=schemas.ServicoOut, status_code=201, dependencies=[Depends(somente_admin)],
             summary="Cadastrar serviço")
def criar(dados: schemas.ServicoCreate, db: Session = Depends(get_db)):
    if crud.obter_servico_por_nome(db, dados.nome):
        raise HTTPException(status_code=409, detail="Já existe um serviço com este nome.")
    return crud.criar_servico(db, dados)


@router.put("/{servico_id}", response_model=schemas.ServicoOut, dependencies=[Depends(somente_admin)],
            summary="Atualizar serviço (parcial)")
def atualizar(servico_id: int, dados: schemas.ServicoUpdate, db: Session = Depends(get_db)):
    s = crud.obter_servico(db, servico_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    if dados.nome:
        outro = crud.obter_servico_por_nome(db, dados.nome)
        if outro and outro.id != servico_id:
            raise HTTPException(status_code=409, detail="Já existe um serviço com este nome.")
    return crud.atualizar_servico(db, s, dados)


@router.delete("/{servico_id}", status_code=204, dependencies=[Depends(somente_admin)], summary="Excluir serviço")
def excluir(servico_id: int, db: Session = Depends(get_db)):
    s = crud.obter_servico(db, servico_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    if crud.servico_possui_agendamentos(db, servico_id):
        raise HTTPException(status_code=409, detail="Serviço com agendamentos vinculados: desative-o em vez de excluir.")
    crud.excluir_servico(db, s)
    return Response(status_code=204)
