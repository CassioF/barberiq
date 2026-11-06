-- =====================================================================
-- BarberIQ / AI Barbershop — schema PostgreSQL 16
-- 7 tabelas: usuarios, servicos, disponibilidade_barbeiro, agendamentos,
--            previsao_noshow, recomendacao_estilo, notificacoes
-- =====================================================================

CREATE TYPE tipo_usuario        AS ENUM ('cliente', 'barbeiro', 'admin');
CREATE TYPE status_agendamento  AS ENUM ('confirmado', 'concluido', 'cancelado', 'faltou');
CREATE TYPE canal_notificacao   AS ENUM ('email', 'whatsapp');
CREATE TYPE tipo_notificacao    AS ENUM ('confirmacao', 'lembrete', 'lembrete_reforcado', 'cancelamento');
CREATE TYPE status_notificacao  AS ENUM ('pendente', 'enviado', 'falha');

CREATE TABLE usuarios (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(120) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    senha_hash  VARCHAR(255) NOT NULL,
    telefone    VARCHAR(20),
    tipo        tipo_usuario NOT NULL,
    ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE servicos (
    id            SERIAL PRIMARY KEY,
    nome          VARCHAR(80)   NOT NULL UNIQUE,
    descricao     VARCHAR(255),
    duracao_min   INTEGER       NOT NULL,
    preco         NUMERIC(10,2) NOT NULL,
    ativo         BOOLEAN       NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_servicos_duracao CHECK (duracao_min > 0),
    CONSTRAINT ck_servicos_preco   CHECK (preco >= 0)
);

CREATE TABLE disponibilidade_barbeiro (
    id          SERIAL PRIMARY KEY,
    barbeiro_id INTEGER  NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    dia_semana  SMALLINT NOT NULL,          -- 0 = segunda ... 6 = domingo
    hora_inicio TIME     NOT NULL,
    hora_fim    TIME     NOT NULL,
    CONSTRAINT ck_disp_dia  CHECK (dia_semana BETWEEN 0 AND 6),
    CONSTRAINT ck_disp_hora CHECK (hora_fim > hora_inicio)
);

CREATE TABLE agendamentos (
    id           SERIAL PRIMARY KEY,
    cliente_id   INTEGER NOT NULL REFERENCES usuarios(id),
    barbeiro_id  INTEGER NOT NULL REFERENCES usuarios(id),
    servico_id   INTEGER NOT NULL REFERENCES servicos(id),
    data_hora    TIMESTAMP NOT NULL,
    status       status_agendamento NOT NULL DEFAULT 'confirmado',
    criado_em    TIMESTAMP NOT NULL DEFAULT NOW()
);
-- Impede dois agendamentos no mesmo horário do barbeiro (UNIQUE barbeiro_id + data_hora),
-- ignorando os cancelados, para que o horário possa ser reaproveitado.
CREATE UNIQUE INDEX uq_barbeiro_horario ON agendamentos (barbeiro_id, data_hora)
    WHERE status <> 'cancelado';
CREATE INDEX ix_agendamentos_cliente ON agendamentos (cliente_id);
CREATE INDEX ix_agendamentos_barbeiro_data ON agendamentos (barbeiro_id, data_hora);

CREATE TABLE previsao_noshow (
    id              SERIAL PRIMARY KEY,
    agendamento_id  INTEGER NOT NULL UNIQUE REFERENCES agendamentos(id) ON DELETE CASCADE,
    risco           NUMERIC(5,4) NOT NULL,
    modelo_versao   VARCHAR(40),
    calculado_em    TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_noshow_risco CHECK (risco BETWEEN 0 AND 1)
);

CREATE TABLE recomendacao_estilo (
    id          SERIAL PRIMARY KEY,
    cliente_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    foto_url    VARCHAR(255),
    sugestoes   JSONB NOT NULL DEFAULT '[]'::jsonb,
    criado_em   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE notificacoes (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    agendamento_id  INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL,
    canal           canal_notificacao  NOT NULL DEFAULT 'email',
    tipo            tipo_notificacao   NOT NULL,
    mensagem        VARCHAR(500) NOT NULL,
    status          status_notificacao NOT NULL DEFAULT 'pendente',
    criado_em       TIMESTAMP NOT NULL DEFAULT NOW(),
    enviado_em      TIMESTAMP
);
CREATE INDEX ix_notificacoes_usuario ON notificacoes (usuario_id);
