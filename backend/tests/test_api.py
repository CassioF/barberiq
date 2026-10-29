from datetime import timedelta

from app import models, tempo
from tests.conftest import login, proxima_segunda

SA = models.StatusAgendamento


def agendar(client, h, barb, servico, quando, **extra):
    return client.post("/agendamentos", headers=h, json={
        "barbeiro_id": barb.id, "servico_id": servico.id, "data_hora": quando.isoformat(), **extra})


# ----------------------------------------------------------------- auth ---
def test_registro_login_e_me(client):
    r = client.post("/auth/registrar", json={"nome": "Novo Cliente", "email": "novo@t.com", "senha": "abc123"})
    assert r.status_code == 201 and r.json()["tipo"] == "cliente" and "senha" not in r.json()
    assert client.post("/auth/registrar", json={"nome": "Outro", "email": "NOVO@t.com", "senha": "abc123"}).status_code == 409
    h = login(client, "novo@t.com", "abc123")
    assert client.get("/auth/me", headers=h).json()["email"] == "novo@t.com"


def test_login_invalido_e_sem_token(client, mundo):
    assert client.post("/auth/login", data={"username": "maria@t.com", "password": "errada"}).status_code == 401
    assert client.get("/agendamentos").status_code == 401


# ------------------------------------------------------------ permissões ---
def test_permissoes_por_perfil(client, mundo):
    hc, hb, ha = (login(client, e) for e in ("maria@t.com", "carlos@t.com", "admin@t.com"))
    assert client.get("/clientes", headers=hc).status_code == 403
    assert client.get("/clientes", headers=hb).status_code == 200
    assert client.post("/barbeiros", headers=hb, json={"nome": "X Y", "email": "x@t.com", "senha": "123456"}).status_code == 403
    assert client.post("/servicos", headers=hc, json={"nome": "Z", "duracao_min": 10, "preco": 1}).status_code == 403
    assert client.get("/relatorios/resumo", headers=hb).status_code == 403
    assert client.get("/relatorios/resumo", headers=ha).status_code == 200


# --------------------------------------------------------------- clientes ---
def test_crud_clientes_admin(client, mundo):
    ha = login(client, "admin@t.com")
    r = client.post("/clientes", headers=ha, json={"nome": "Ana Costa", "email": "ana@t.com", "senha": "123456"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/clientes", headers=ha, json={"nome": "Ana 2", "email": "ana@t.com", "senha": "123456"}).status_code == 409
    r = client.get("/clientes?busca=ANA", headers=ha)
    assert [c["id"] for c in r.json()] == [cid] and r.headers["X-Total-Count"] == "1"
    assert client.put(f"/clientes/{cid}", headers=ha, json={"telefone": "34988887777"}).json()["telefone"] == "34988887777"
    # um barbeiro não é enxergado pelo CRUD de clientes
    assert client.get(f"/clientes/{mundo['barb'].id}", headers=ha).status_code == 404
    assert client.delete(f"/clientes/{cid}", headers=ha).status_code == 204


def test_excluir_cliente_com_agendamento_bloqueado(client, mundo):
    ha, hc = login(client, "admin@t.com"), login(client, "maria@t.com")
    quando = proxima_segunda().replace(hour=9)
    assert agendar(client, hc, mundo["barb"], mundo["corte"], quando).status_code == 201
    assert client.delete(f"/clientes/{mundo['c1'].id}", headers=ha).status_code == 409


# ------------------------------------------------------------ agendamento ---
def test_horarios_livres_respeitam_janelas_e_duracao(client, mundo):
    hc = login(client, "maria@t.com")
    seg = proxima_segunda()
    q = f"barbeiro_id={mundo['barb'].id}&data={seg.date()}"
    corte = client.get(f"/agendamentos/horarios-livres?{q}&servico_id={mundo['corte'].id}", headers=hc).json()["horarios"]
    horas = [h[11:16] for h in corte]
    assert horas[0] == "09:00" and "12:00" not in horas and "12:30" not in horas and "13:00" in horas
    assert horas[-1] == "17:30"
    combo = [h[11:16] for h in client.get(f"/agendamentos/horarios-livres?{q}&servico_id={mundo['combo'].id}", headers=hc).json()["horarios"]]
    assert "11:00" in combo and "11:30" not in combo and combo[-1] == "17:00"  # 60 min não atravessa o almoço
    sab = seg + timedelta(days=5)
    assert client.get(f"/agendamentos/horarios-livres?barbeiro_id={mundo['barb'].id}&servico_id={mundo['corte'].id}&data={sab.date()}",
                      headers=hc).json()["horarios"] == []


def test_conflito_de_horario_e_sobreposicao(client, mundo):
    h1, h2 = login(client, "maria@t.com"), login(client, "joao@t.com")
    seg = proxima_segunda()
    assert agendar(client, h1, mundo["barb"], mundo["combo"], seg.replace(hour=10)).status_code == 201  # 10:00-11:00
    assert agendar(client, h2, mundo["barb"], mundo["corte"], seg.replace(hour=10)).status_code == 409
    assert agendar(client, h2, mundo["barb"], mundo["corte"], seg.replace(hour=10, minute=30)).status_code == 409
    assert agendar(client, h2, mundo["barb"], mundo["corte"], seg.replace(hour=11)).status_code == 201
    # fora da janela de trabalho e no passado
    assert agendar(client, h2, mundo["barb"], mundo["corte"], seg.replace(hour=12)).status_code == 409
    assert agendar(client, h2, mundo["barb"], mundo["corte"], tempo.agora() - timedelta(days=1)).status_code == 422


def test_cliente_nao_agenda_dois_lugares_ao_mesmo_tempo(client, db, mundo):
    h1 = login(client, "maria@t.com")
    outro = models.Usuario(nome="Rafael", email="rafa@t.com", tipo=models.TipoUsuario.barbeiro, senha_hash="x")
    db.add(outro)
    db.flush()
    db.add(models.DisponibilidadeBarbeiro(barbeiro_id=outro.id, dia_semana=0, hora_inicio=__import__("datetime").time(9), hora_fim=__import__("datetime").time(12)))
    db.commit()
    seg = proxima_segunda().replace(hour=9)
    assert agendar(client, h1, mundo["barb"], mundo["corte"], seg).status_code == 201
    assert agendar(client, h1, outro, mundo["corte"], seg).status_code == 409


def test_cancelar_libera_horario_e_notifica(client, mundo):
    h1, h2 = login(client, "maria@t.com"), login(client, "joao@t.com")
    seg = proxima_segunda().replace(hour=9)
    ag = agendar(client, h1, mundo["barb"], mundo["corte"], seg).json()
    assert client.patch(f"/agendamentos/{ag['id']}/cancelar", headers=h2).status_code == 404  # não é dele
    assert client.patch(f"/agendamentos/{ag['id']}/cancelar", headers=h1).json()["status"] == "cancelado"
    assert client.patch(f"/agendamentos/{ag['id']}/cancelar", headers=h1).status_code == 409
    assert agendar(client, h2, mundo["barb"], mundo["corte"], seg).status_code == 201
    tipos = [n["tipo"] for n in client.get("/notificacoes/minhas", headers=h1).json()]
    assert sorted(tipos) == ["cancelamento", "confirmacao"]


def test_visibilidade_e_risco(client, mundo):
    hc, hb = login(client, "maria@t.com"), login(client, "carlos@t.com")
    seg = proxima_segunda().replace(hour=9)
    saida_cliente = agendar(client, hc, mundo["barb"], mundo["corte"], seg).json()
    assert saida_cliente["risco_noshow"] is None  # cliente não vê o risco
    ags_b = client.get("/agendamentos", headers=hb).json()
    assert len(ags_b) == 1 and 0 <= ags_b[0]["risco_noshow"] <= 1 and ags_b[0]["nivel_risco"] in ("baixo", "medio", "alto")
    assert client.get("/agendamentos", headers=login(client, "joao@t.com")).json() == []
    assert client.get(f"/agendamentos/{saida_cliente['id']}", headers=login(client, "joao@t.com")).status_code == 404


def test_barbeiro_marca_concluido_e_faltou(client, db, mundo):
    hb, hc = login(client, "carlos@t.com"), login(client, "maria@t.com")
    futuro = agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).json()
    assert client.patch(f"/agendamentos/{futuro['id']}/status", headers=hb, json={"status": "concluido"}).status_code == 409
    assert client.patch(f"/agendamentos/{futuro['id']}/status", headers=hc, json={"status": "faltou"}).status_code == 403
    passado = models.Agendamento(cliente_id=mundo["c1"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                                 data_hora=tempo.agora() - timedelta(days=1))
    db.add(passado)
    db.commit()
    r = client.patch(f"/agendamentos/{passado.id}/status", headers=hb, json={"status": "faltou"})
    assert r.status_code == 200 and r.json()["status"] == "faltou"


# ------------------------------------------------------------------- IA ---
def test_historico_de_faltas_aumenta_risco(client, db, mundo):
    """Cliente faltoso recebe risco maior que cliente pontual para o mesmo horário."""
    base = tempo.agora() - timedelta(days=30)
    for i in range(6):
        db.add(models.Agendamento(cliente_id=mundo["c1"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                                  data_hora=base + timedelta(days=i), status=SA.faltou))
        db.add(models.Agendamento(cliente_id=mundo["c2"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                                  data_hora=base + timedelta(days=i, hours=1), status=SA.concluido))
    db.commit()
    seg = proxima_segunda(dias_min=10)
    agendar(client, login(client, "maria@t.com"), mundo["barb"], mundo["corte"], seg.replace(hour=9))
    agendar(client, login(client, "joao@t.com"), mundo["barb"], mundo["corte"], seg.replace(hour=10))
    ags = {a["cliente"]["nome"]: a for a in client.get("/agendamentos", headers=login(client, "carlos@t.com")).json()}
    assert ags["Maria"]["risco_noshow"] > 0.5 > ags["João"]["risco_noshow"]
    assert ags["Maria"]["nivel_risco"] == "alto"


def test_ia_prever_e_metricas(client, mundo):
    hb = login(client, "carlos@t.com")
    baixo = client.post("/ia/noshow/prever", headers=hb, json={"taxa_faltas": 0, "dia_semana": 2, "antecedencia_horas": 24}).json()
    alto = client.post("/ia/noshow/prever", headers=hb, json={"taxa_faltas": 0.6, "dia_semana": 4, "antecedencia_horas": 200}).json()
    assert alto["risco"] > baixo["risco"] and alto["nivel"] == "alto"
    m = client.get("/ia/noshow/metricas", headers=hb).json()
    assert m["auc_roc"] > 0.5 and 0 < m["acuracia"] <= 1
    assert client.post("/ia/noshow/treinar", headers=hb).status_code == 403


# ---------------------------------------------------- notificações/lembretes ---
def test_lembretes_normal_e_reforcado(client, db, mundo):
    ha = login(client, "admin@t.com")
    agora = tempo.agora()
    a1 = models.Agendamento(cliente_id=mundo["c1"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                            data_hora=agora + timedelta(hours=20))   # risco baixo -> lembrete (24h)
    a2 = models.Agendamento(cliente_id=mundo["c2"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                            data_hora=agora + timedelta(hours=40))   # risco alto -> reforçado (48h)
    a3 = models.Agendamento(cliente_id=mundo["c1"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                            data_hora=agora + timedelta(hours=40, minutes=30))  # baixo, ainda fora da janela
    db.add_all([a1, a2, a3])
    db.flush()
    db.add_all([models.PrevisaoNoShow(agendamento_id=a1.id, risco=0.1), models.PrevisaoNoShow(agendamento_id=a2.id, risco=0.8),
                models.PrevisaoNoShow(agendamento_id=a3.id, risco=0.1)])
    db.commit()
    assert client.post("/notificacoes/disparar-lembretes", headers=ha).json() == {"enviados": 2}
    assert client.post("/notificacoes/disparar-lembretes", headers=ha).json() == {"enviados": 0}  # não repete
    tipos = {n["agendamento_id"]: n["tipo"] for n in client.get("/notificacoes", headers=ha).json()}
    assert tipos == {a1.id: "lembrete", a2.id: "lembrete_reforcado"}


# -------------------------------------------------------------- relatórios ---
def test_relatorio_resumo(client, db, mundo):
    ha = login(client, "admin@t.com")
    ontem = tempo.agora().replace(hour=10, minute=0, second=0) - timedelta(days=1)
    for i, st in enumerate([SA.concluido, SA.concluido, SA.faltou, SA.cancelado]):
        db.add(models.Agendamento(cliente_id=mundo["c1"].id, barbeiro_id=mundo["barb"].id, servico_id=mundo["corte"].id,
                                  data_hora=ontem + timedelta(minutes=30 * i), status=st))
    db.commit()
    r = client.get("/relatorios/resumo", headers=ha).json()
    assert r["faturamento_total"] == 90.0 and r["ticket_medio"] == 45.0
    assert r["por_status"]["concluido"] == 2 and r["agendamentos_total"] == 4
    assert abs(r["taxa_noshow"] - 1 / 3) < 0.001 and r["taxa_cancelamento"] == 0.25
    assert r["faturamento_por_servico"][0]["servico"] == "Corte"
    assert 0 < r["ocupacao_geral"] <= 1
    assert client.get("/relatorios/resumo?data_de=2026-01-10&data_ate=2026-01-01", headers=ha).status_code == 422


# ------------------------------------------------------------ disponibilidade ---
def test_barbeiro_edita_propria_disponibilidade(client, mundo):
    hb, hc = login(client, "carlos@t.com"), login(client, "maria@t.com")
    bid = mundo["barb"].id
    novo = [{"dia_semana": 0, "hora_inicio": "08:00:00", "hora_fim": "12:00:00"}]
    assert client.put(f"/barbeiros/{bid}/disponibilidade", headers=hc, json=novo).status_code == 403
    r = client.put(f"/barbeiros/{bid}/disponibilidade", headers=hb, json=novo)
    assert r.status_code == 200 and len(r.json()) == 1
    sobreposto = novo + [{"dia_semana": 0, "hora_inicio": "11:00:00", "hora_fim": "14:00:00"}]
    assert client.put(f"/barbeiros/{bid}/disponibilidade", headers=hb, json=sobreposto).status_code == 422
