"""
Schemas Pydantic: validação de entrada e formatação de saída da API.
A senha só aparece na entrada; nunca é devolvida.
"""
from datetime import datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import (
    CanalNotificacao, StatusAgendamento, StatusNotificacao, TipoNotificacao,
)


# ------------------------------------------------------------- usuários ---
class UsuarioBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120, examples=["Maria Silva"])
    email: EmailStr = Field(..., examples=["maria.silva@email.com"])
    telefone: Optional[str] = Field(None, max_length=20, examples=["34999990002"])


class UsuarioCreate(UsuarioBase):
    senha: str = Field(..., min_length=6, max_length=72, examples=["minhaSenha123"])


class UsuarioUpdate(BaseModel):
    """Todos os campos opcionais: só o que for enviado é atualizado."""
    nome: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    telefone: Optional[str] = Field(None, max_length=20)
    senha: Optional[str] = Field(None, min_length=6, max_length=72)
    ativo: Optional[bool] = None


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    ativo: bool
    criado_em: datetime


# Nomes usados no CRUD de clientes original
ClienteCreate = UsuarioCreate
ClienteUpdate = UsuarioUpdate
ClienteOut = UsuarioOut
BarbeiroCreate = UsuarioCreate
BarbeiroUpdate = UsuarioUpdate
BarbeiroOut = UsuarioOut


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


# --------------------------------------------------------------- serviços ---
class ServicoBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=80, examples=["Corte"])
    descricao: Optional[str] = Field(None, max_length=255)
    duracao_min: int = Field(..., gt=0, le=480, examples=[30])
    preco: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2, examples=["45.00"])


class ServicoCreate(ServicoBase):
    pass


class ServicoUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=80)
    descricao: Optional[str] = Field(None, max_length=255)
    duracao_min: Optional[int] = Field(None, gt=0, le=480)
    preco: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=2)
    ativo: Optional[bool] = None


class ServicoOut(ServicoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool


# ---------------------------------------------------------- disponibilidade ---
class DisponibilidadeIn(BaseModel):
    dia_semana: int = Field(..., ge=0, le=6, description="0 = segunda ... 6 = domingo")
    hora_inicio: time
    hora_fim: time

    @field_validator("hora_fim")
    @classmethod
    def fim_depois_do_inicio(cls, v, info):
        ini = info.data.get("hora_inicio")
        if ini and v <= ini:
            raise ValueError("hora_fim deve ser maior que hora_inicio")
        return v


class DisponibilidadeOut(DisponibilidadeIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barbeiro_id: int


# ------------------------------------------------------------ agendamentos ---
class AgendamentoCreate(BaseModel):
    barbeiro_id: int
    servico_id: int
    data_hora: datetime = Field(..., examples=["2026-10-20T14:00:00"])
    cliente_id: Optional[int] = Field(None, description="Só admin: agenda em nome de um cliente")


class AgendamentoStatusIn(BaseModel):
    status: StatusAgendamento


class PessoaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: Optional[str] = None


class ServicoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    duracao_min: int
    preco: Decimal


class AgendamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_hora: datetime
    status: StatusAgendamento
    cliente: PessoaResumo
    barbeiro: PessoaResumo
    servico: ServicoResumo
    # Preenchidos apenas para barbeiro/admin (o cliente não vê o risco)
    risco_noshow: Optional[float] = None
    nivel_risco: Optional[str] = None


class HorariosLivresOut(BaseModel):
    data: str
    horarios: list[datetime]


# ----------------------------------------------------------- notificações ---
class NotificacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    agendamento_id: Optional[int]
    canal: CanalNotificacao
    tipo: TipoNotificacao
    mensagem: str
    status: StatusNotificacao
    criado_em: datetime
    enviado_em: Optional[datetime]


# --------------------------------------------------------------------- IA ---
class PrevisaoIn(BaseModel):
    taxa_faltas: float = Field(..., ge=0, le=1, examples=[0.2])
    dia_semana: int = Field(..., ge=0, le=6, examples=[4])
    antecedencia_horas: float = Field(..., ge=0, le=2000, examples=[72])


class PrevisaoOut(BaseModel):
    risco: float
    nivel: str
