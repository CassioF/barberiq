"""Chatbot: a chamada à API da Anthropic é simulada; as ferramentas rodam de verdade no banco de teste."""
import json
from types import SimpleNamespace as NS

import pytest

from app import chat, models
from app.config import settings
from tests.conftest import login, proxima_segunda

SA = models.StatusAgendamento


def _texto(t):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=t)])


def _ferramenta(nome, args, id_="t1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id=id_, name=nome, input=args)])


@pytest.fixture()
def com_chave(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "chave-de-teste")


def _roteiro(monkeypatch, passos):
    """Faz o 'modelo' devolver as respostas da lista, em ordem, e guarda o que recebeu."""
    recebidas = []

    def falso(system, mensagens):
        recebidas.append(list(mensagens))
        return passos.pop(0)

    monkeypatch.setattr(chat, "_chamar_modelo", falso)
    return recebidas


def _resultado(recebidas, i):
    """Conteúdo do tool_result enviado ao modelo na chamada i."""
    return json.loads(recebidas[i][-1]["content"][0]["content"])


def test_status_e_sem_chave(client, mundo, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    hc = login(client, "maria@t.com")
    assert client.get("/chat/status", headers=hc).json() == {"ia": False}
    r = client.post("/chat", headers=hc, json={"mensagens": [{"papel": "user", "texto": "oi"}]})
    assert r.status_code == 503


def test_somente_cliente_usa_o_chat(client, mundo, com_chave):
    for email in ("carlos@t.com", "admin@t.com"):
        r = client.post("/chat", headers=login(client, email), json={"mensagens": [{"papel": "user", "texto": "oi"}]})
        assert r.status_code == 403
    assert client.post("/chat", json={"mensagens": [{"papel": "user", "texto": "oi"}]}).status_code == 401


def test_agenda_pela_conversa(client, db, mundo, com_chave, monkeypatch):
    seg = proxima_segunda()
    b, corte = mundo["barb"], mundo["corte"]
    recebidas = _roteiro(monkeypatch, [
        _ferramenta("listar_servicos", {}),
        _ferramenta("horarios_livres", {"servico_id": corte.id, "barbeiro_id": b.id, "data": seg.date().isoformat()}),
        _ferramenta("criar_agendamento", {"servico_id": corte.id, "barbeiro_id": b.id,
                                          "data_hora": seg.replace(hour=9).strftime("%Y-%m-%dT%H:%M")}),
        _texto("Pronto! Corte marcado."),
    ])
    hc = login(client, "maria@t.com")
    r = client.post("/chat", headers=hc, json={"mensagens": [
        {"papel": "assistant", "texto": "Olá! Como posso ajudar?"},  # saudação do front é descartada
        {"papel": "user", "texto": "quero cortar segunda às 9h com o Carlos"},
        {"papel": "assistant", "texto": "Confirma corte segunda 09h com Carlos, R$ 45?"},
        {"papel": "user", "texto": "sim"},
    ]})
    assert r.status_code == 200, r.text
    assert r.json() == {"resposta": "Pronto! Corte marcado.", "atualizou": True}
    assert recebidas[0][0] == {"role": "user", "content": "quero cortar segunda às 9h com o Carlos"}
    assert any(s["nome"] == "Corte" for s in _resultado(recebidas, 1)["servicos"])
    assert "09:00" in _resultado(recebidas, 2)["horarios"]
    criado = _resultado(recebidas, 3)
    assert criado["ok"] and criado["barbeiro"] == "Carlos"
    ag = db.get(models.Agendamento, criado["agendamento_id"])
    assert ag.cliente_id == mundo["c1"].id and ag.status == SA.confirmado
    assert "risco" not in json.dumps(criado)  # o cliente nunca recebe o risco


def test_regras_da_api_valem_no_chat(client, db, mundo, com_chave, monkeypatch):
    seg = proxima_segunda()
    b, corte = mundo["barb"], mundo["corte"]
    quando = seg.replace(hour=10).strftime("%Y-%m-%dT%H:%M")
    hj = login(client, "joao@t.com")
    assert client.post("/agendamentos", headers=hj, json={"barbeiro_id": b.id, "servico_id": corte.id,
                                                          "data_hora": quando}).status_code == 201
    ag_joao = db.query(models.Agendamento).one()
    recebidas = _roteiro(monkeypatch, [
        _ferramenta("criar_agendamento", {"servico_id": corte.id, "barbeiro_id": b.id, "data_hora": quando}),
        _ferramenta("cancelar_agendamento", {"agendamento_id": ag_joao.id}),
        _ferramenta("horarios_livres", {"servico_id": corte.id, "barbeiro_id": b.id, "data": "amanhã"}),
        _texto("Esse horário está ocupado."),
    ])
    r = client.post("/chat", headers=login(client, "maria@t.com"),
                    json={"mensagens": [{"papel": "user", "texto": "segunda 10h"}]})
    assert r.status_code == 200 and r.json()["atualizou"] is False
    assert "erro" in _resultado(recebidas, 1)                                  # conflito de horário
    assert _resultado(recebidas, 2) == {"erro": "Agendamento não encontrado."}  # não cancela o de outro cliente
    assert "erro" in _resultado(recebidas, 3)                                  # data inválida
    db.refresh(ag_joao)
    assert ag_joao.status == SA.confirmado and db.query(models.Agendamento).count() == 1


def test_lista_e_cancela_os_proprios(client, db, mundo, com_chave, monkeypatch):
    seg = proxima_segunda()
    hc = login(client, "maria@t.com")
    client.post("/agendamentos", headers=hc, json={"barbeiro_id": mundo["barb"].id, "servico_id": mundo["corte"].id,
                                                   "data_hora": seg.replace(hour=14).isoformat()})
    ag = db.query(models.Agendamento).one()
    recebidas = _roteiro(monkeypatch, [
        _ferramenta("meus_agendamentos", {}),
        _ferramenta("cancelar_agendamento", {"agendamento_id": ag.id}),
        _texto("Cancelado."),
    ])
    r = client.post("/chat", headers=hc, json={"mensagens": [{"papel": "user", "texto": "cancela meu horário"}]})
    assert r.json() == {"resposta": "Cancelado.", "atualizou": True}
    assert [a["id"] for a in _resultado(recebidas, 1)["agendamentos"]] == [ag.id]
    db.refresh(ag)
    assert ag.status == SA.cancelado


def test_falha_do_modelo_vira_503(client, mundo, com_chave, monkeypatch):
    def quebra(system, mensagens):
        raise RuntimeError("timeout")
    monkeypatch.setattr(chat, "_chamar_modelo", quebra)
    r = client.post("/chat", headers=login(client, "maria@t.com"), json={"mensagens": [{"papel": "user", "texto": "oi"}]})
    assert r.status_code == 503
