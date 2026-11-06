"""
Modelos SQLAlchemy — espelham o schema_barberiq.sql (7 tabelas).
"""
import enum

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, SmallInteger, String, Time, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class TipoUsuario(str, enum.Enum):
    cliente = "cliente"
    barbeiro = "barbeiro"
    admin = "admin"


class StatusAgendamento(str, enum.Enum):
    confirmado = "confirmado"
    concluido = "concluido"
    cancelado = "cancelado"
    faltou = "faltou"


class CanalNotificacao(str, enum.Enum):
    email = "email"
    whatsapp = "whatsapp"


class TipoNotificacao(str, enum.Enum):
    confirmacao = "confirmacao"
    lembrete = "lembrete"
    lembrete_reforcado = "lembrete_reforcado"
    cancelamento = "cancelamento"


class StatusNotificacao(str, enum.Enum):
    pendente = "pendente"
    enviado = "enviado"
    falha = "falha"


def _enum(cls, nome):
    return Enum(cls, name=nome)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=True)
    tipo = Column(_enum(TipoUsuario, "tipo_usuario"), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    agendamentos_como_cliente = relationship(
        "Agendamento", foreign_keys="Agendamento.cliente_id", back_populates="cliente"
    )
    agendamentos_como_barbeiro = relationship(
        "Agendamento", foreign_keys="Agendamento.barbeiro_id", back_populates="barbeiro"
    )
    disponibilidades = relationship(
        "DisponibilidadeBarbeiro", back_populates="barbeiro", cascade="all, delete-orphan"
    )


class Servico(Base):
    __tablename__ = "servicos"
    __table_args__ = (
        CheckConstraint("duracao_min > 0", name="ck_servicos_duracao"),
        CheckConstraint("preco >= 0", name="ck_servicos_preco"),
    )

    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    duracao_min = Column(Integer, nullable=False)
    preco = Column(Numeric(10, 2), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")


class DisponibilidadeBarbeiro(Base):
    __tablename__ = "disponibilidade_barbeiro"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="ck_disp_dia"),
        CheckConstraint("hora_fim > hora_inicio", name="ck_disp_hora"),
    )

    id = Column(Integer, primary_key=True)
    barbeiro_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    dia_semana = Column(SmallInteger, nullable=False)  # 0 = segunda ... 6 = domingo
    hora_inicio = Column(Time, nullable=False)
    hora_fim = Column(Time, nullable=False)

    barbeiro = relationship("Usuario", back_populates="disponibilidades")


class Agendamento(Base):
    __tablename__ = "agendamentos"
    __table_args__ = (
        # Índice único parcial: impede dois agendamentos no mesmo horário, mas um
        # agendamento cancelado libera o horário para outro cliente.
        Index(
            "uq_barbeiro_horario", "barbeiro_id", "data_hora", unique=True,
            postgresql_where=text("status <> 'cancelado'"),
            sqlite_where=text("status <> 'cancelado'"),
        ),
        Index("ix_agendamentos_barbeiro_data", "barbeiro_id", "data_hora"),
    )

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    barbeiro_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    data_hora = Column(DateTime, nullable=False)
    status = Column(
        _enum(StatusAgendamento, "status_agendamento"),
        nullable=False,
        default=StatusAgendamento.confirmado,
        server_default="confirmado",
    )
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    cliente = relationship("Usuario", foreign_keys=[cliente_id], back_populates="agendamentos_como_cliente")
    barbeiro = relationship("Usuario", foreign_keys=[barbeiro_id], back_populates="agendamentos_como_barbeiro")
    servico = relationship("Servico")
    previsao = relationship(
        "PrevisaoNoShow", back_populates="agendamento", uselist=False, cascade="all, delete-orphan"
    )


class PrevisaoNoShow(Base):
    __tablename__ = "previsao_noshow"
    __table_args__ = (CheckConstraint("risco BETWEEN 0 AND 1", name="ck_noshow_risco"),)

    id = Column(Integer, primary_key=True)
    agendamento_id = Column(
        Integer, ForeignKey("agendamentos.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    risco = Column(Numeric(5, 4), nullable=False)
    modelo_versao = Column(String(40), nullable=True)
    calculado_em = Column(DateTime, nullable=False, server_default=func.now())

    agendamento = relationship("Agendamento", back_populates="previsao")


class RecomendacaoEstilo(Base):
    __tablename__ = "recomendacao_estilo"

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    foto_url = Column(String(255), nullable=True)
    sugestoes = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id", ondelete="SET NULL"), nullable=True)
    canal = Column(_enum(CanalNotificacao, "canal_notificacao"), nullable=False, default=CanalNotificacao.email)
    tipo = Column(_enum(TipoNotificacao, "tipo_notificacao"), nullable=False)
    mensagem = Column(String(500), nullable=False)
    status = Column(_enum(StatusNotificacao, "status_notificacao"), nullable=False, default=StatusNotificacao.pendente)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    enviado_em = Column(DateTime, nullable=True)
