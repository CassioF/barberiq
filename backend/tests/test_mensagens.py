"""Envio real por Telegram / WhatsApp (com o HTTP dos provedores simulado)."""
import httpx
import pytest

from app import mensageiros, models
from app.config import settings
from tests.conftest import login, proxima_segunda
from tests.test_api import agendar


@pytest.fixture()
def chamadas(monkeypatch):
    """Intercepta httpx.post: nada sai para a internet; guarda (url, json)."""
    feitas = []

    def falso_post(url, json=None, **_):
        feitas.append((url, json))
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(mensageiros.httpx, "post", falso_post)
    return feitas


@pytest.fixture()
def telegram(monkeypatch, chamadas):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "BarberIQBot")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "segredo")
    return chamadas


def _start(client, codigo, chat_id=555, segredo="segredo"):
    return client.post("/notificacoes/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": segredo},
                       json={"update_id": 1, "message": {"chat": {"id": chat_id}, "text": f"/start {codigo}"}})


def test_sem_configuracao_continua_simulado(client, mundo, chamadas):
    hc = login(client, "maria@t.com")
    c = client.get("/notificacoes/canais", headers=hc).json()
    assert c["telegram_ativo"] is False and c["whatsapp_ativo"] is False and c["canal_atual"] == "whatsapp"
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    assert chamadas == []  # nenhuma chamada externa
    n = client.get("/notificacoes/minhas", headers=hc).json()[0]
    assert n["tipo"] == "confirmacao" and n["status"] == "enviado"


def test_vincular_telegram_e_receber_confirmacao(client, db, mundo, telegram):
    hc = login(client, "maria@t.com")
    link = client.get("/notificacoes/canais", headers=hc).json()["telegram_link"]
    assert link.startswith("https://t.me/BarberIQBot?start=")
    codigo = link.split("start=")[1]

    assert _start(client, codigo, segredo="errado").status_code == 403
    assert _start(client, codigo).status_code == 200
    db.expire_all()
    assert db.get(models.Usuario, mundo["c1"].id).telegram_chat_id == "555"
    assert "conectado" in telegram[-1][1]["text"]  # o bot respondeu

    c = client.get("/notificacoes/canais", headers=hc).json()
    assert c["telegram_vinculado"] and c["canal_atual"] == "telegram"

    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    url, corpo = telegram[-1]
    assert url.endswith("/bot123:ABC/sendMessage") and corpo["chat_id"] == "555"
    assert "confirmado" in corpo["text"] and "Corte" in corpo["text"]
    n = client.get("/notificacoes/minhas", headers=hc).json()[0]
    assert n["canal"] == "telegram" and n["status"] == "enviado"

    assert client.delete("/notificacoes/telegram", headers=hc).status_code == 204
    assert client.get("/notificacoes/canais", headers=hc).json()["canal_atual"] == "whatsapp"


def test_codigo_de_vinculo_adulterado_nao_vincula(client, db, mundo, telegram):
    codigo = mensageiros.codigo_vinculo(mundo["c1"].id)
    outro = f"{mundo['c2'].id}_{codigo.split('_')[1]}"  # assinatura de outro usuário
    assert _start(client, outro).status_code == 200
    db.expire_all()
    assert db.get(models.Usuario, mundo["c2"].id).telegram_chat_id is None


def test_whatsapp_cloud_api(client, mundo, chamadas, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "999")
    hc = login(client, "maria@t.com")
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    url, corpo = chamadas[-1]
    assert url.endswith("/999/messages") and corpo["to"] == "5534999990000"
    assert corpo["type"] == "text" and "confirmado" in corpo["text"]["body"]

    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE", "barberiq_aviso")
    assert client.post("/notificacoes/teste", headers=hc).json()["canal"] == "whatsapp"
    corpo = chamadas[-1][1]
    assert corpo["type"] == "template" and corpo["template"]["name"] == "barberiq_aviso"


def test_falha_do_provedor_nao_derruba_agendamento(client, mundo, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "999")
    monkeypatch.setattr(mensageiros.httpx, "post",
                        lambda *a, **k: httpx.Response(401, json={"error": {"message": "token inválido"}}))
    hc = login(client, "maria@t.com")
    assert agendar(client, hc, mundo["barb"], mundo["corte"], proxima_segunda().replace(hour=9)).status_code == 201
    assert client.get("/notificacoes/minhas", headers=hc).json()[0]["status"] == "falha"


def test_numero_whatsapp():
    assert mensageiros.numero_whatsapp("(34) 99999-0002") == "5534999990002"
    assert mensageiros.numero_whatsapp("+55 34 99999-0002") == "5534999990002"
