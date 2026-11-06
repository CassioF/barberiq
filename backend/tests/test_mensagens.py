"""Envio real pelo WhatsApp (com o HTTP da Meta simulado)."""
import httpx
import pytest

from app import mensageiros
from app.config import settings
from tests.conftest import login, proxima_segunda
from tests.test_api import agendar


@pytest.fixture()
def chamadas(monkeypatch):
    """Intercepta httpx.post: nada sai para a internet; guarda (url, json)."""
    feitas = []

    def falso_post(url, json=None, **_):
        feitas.append((url, json))
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    monkeypatch.setattr(mensageiros.httpx, "post", falso_post)
    return feitas


@pytest.fixture()
def whatsapp(monkeypatch, chamadas):
    monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "999")
    return chamadas


def test_sem_configuracao_continua_simulado(client, mundo, chamadas):
    hc = login(client, "maria@t.com")
    c = client.get("/notificacoes/canais", headers=hc).json()
    assert c["whatsapp_ativo"] is False and c["canal_atual"] == "whatsapp"
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    assert chamadas == []  # nenhuma chamada externa
    n = client.get("/notificacoes/minhas", headers=hc).json()[0]
    assert n["tipo"] == "confirmacao" and n["status"] == "enviado"


def test_confirmacao_pelo_whatsapp(client, mundo, whatsapp):
    hc = login(client, "maria@t.com")
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    url, corpo = whatsapp[-1]
    assert url.endswith("/999/messages") and corpo["to"] == "5534999990000"
    assert corpo["type"] == "text" and "confirmado" in corpo["text"]["body"] and "Corte" in corpo["text"]["body"]
    n = client.get("/notificacoes/minhas", headers=hc).json()[0]
    assert n["canal"] == "whatsapp" and n["status"] == "enviado"


def test_template_aprovado(client, mundo, whatsapp, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE", "barberiq_aviso")
    hc = login(client, "maria@t.com")
    assert client.post("/notificacoes/teste", headers=hc).json()["status"] == "enviado"
    corpo = whatsapp[-1][1]
    assert corpo["type"] == "template" and corpo["template"]["name"] == "barberiq_aviso"
    assert "teste" in corpo["template"]["components"][0]["parameters"][0]["text"]


def test_cliente_troca_e_remove_numero(client, mundo, whatsapp):
    hc = login(client, "maria@t.com")
    r = client.put("/notificacoes/whatsapp", headers=hc, json={"telefone": "(34) 98888-7777"})
    assert r.status_code == 200 and r.json()["telefone"] == "(34) 98888-7777"
    client.post("/notificacoes/teste", headers=hc)
    assert whatsapp[-1][1]["to"] == "5534988887777"
    assert client.put("/notificacoes/whatsapp", headers=hc, json={"telefone": "123"}).status_code == 422
    r = client.put("/notificacoes/whatsapp", headers=hc, json={"telefone": ""})
    assert r.json()["telefone"] is None and r.json()["canal_atual"] == "email"


def test_falha_do_whatsapp_nao_derruba_agendamento(client, mundo, whatsapp, monkeypatch):
    monkeypatch.setattr(mensageiros.httpx, "post",
                        lambda *a, **k: httpx.Response(401, json={"error": {"message": "token inválido"}}))
    hc = login(client, "maria@t.com")
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    assert client.get("/notificacoes/minhas", headers=hc).json()[0]["status"] == "falha"


def test_numero_whatsapp():
    assert mensageiros.numero_whatsapp("(34) 99999-0002") == "5534999990002"
    assert mensageiros.numero_whatsapp("+55 34 99999-0002") == "5534999990002"
