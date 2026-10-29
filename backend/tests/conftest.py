import os
import tempfile
from datetime import datetime, time, timedelta

# Banco de teste: SQLite em arquivo temporário, a menos que TEST_DATABASE_URL seja informado
# (ex.: um PostgreSQL de teste — o conteúdo desse banco é APAGADO a cada teste).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/teste.db")
os.environ["LEMBRETES_INTERVALO_MIN"] = "0"
os.environ["SECRET_KEY"] = "teste"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models, tempo  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_senha  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c


def _u(db, nome, email, tipo, senha="senha123"):
    u = models.Usuario(nome=nome, email=email, tipo=tipo, senha_hash=hash_senha(senha), telefone="34999990000")
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def mundo(db):
    """admin, 1 barbeiro (seg-sex 9-12 e 13-18), 2 clientes e 2 serviços."""
    admin = _u(db, "Admin", "admin@t.com", models.TipoUsuario.admin)
    barb = _u(db, "Carlos", "carlos@t.com", models.TipoUsuario.barbeiro)
    c1 = _u(db, "Maria", "maria@t.com", models.TipoUsuario.cliente)
    c2 = _u(db, "João", "joao@t.com", models.TipoUsuario.cliente)
    corte = models.Servico(nome="Corte", duracao_min=30, preco=45)
    combo = models.Servico(nome="Combo", duracao_min=60, preco=75)
    db.add_all([corte, combo])
    db.flush()
    for d in range(5):
        db.add(models.DisponibilidadeBarbeiro(barbeiro_id=barb.id, dia_semana=d, hora_inicio=time(9), hora_fim=time(12)))
        db.add(models.DisponibilidadeBarbeiro(barbeiro_id=barb.id, dia_semana=d, hora_inicio=time(13), hora_fim=time(18)))
    db.commit()
    return dict(admin=admin, barb=barb, c1=c1, c2=c2, corte=corte, combo=combo)


def proxima_segunda(dias_min=3) -> datetime:
    """Uma segunda-feira futura (pelo menos `dias_min` dias à frente), meia-noite."""
    d = tempo.agora().replace(hour=0, minute=0, second=0) + timedelta(days=dias_min)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def login(client, email, senha="senha123"):
    r = client.post("/auth/login", data={"username": email, "password": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
