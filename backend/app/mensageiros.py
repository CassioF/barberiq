"""
Provedores reais de mensagem: Telegram (Bot API) e WhatsApp (Meta Cloud API).

Cada provedor só é usado quando as variáveis de ambiente dele estão preenchidas;
sem elas, o envio continua SIMULADO (log) — assim a demo e os testes funcionam
sem nenhuma conta externa.

Telegram : TELEGRAM_BOT_TOKEN (+ TELEGRAM_BOT_USERNAME para o link de vínculo)
WhatsApp : WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID (+ WHATSAPP_TEMPLATE opcional)
"""
import hashlib
import hmac
import logging
import re

import httpx

from app.config import settings

log = logging.getLogger("barberiq.mensageiros")
TIMEOUT = httpx.Timeout(10.0)


class ErroEnvio(Exception):
    """O provedor recusou a mensagem (token inválido, número sem WhatsApp...)."""


# ------------------------------------------------------------------ Telegram ---
def telegram_ativo() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def _tg(metodo: str, **dados) -> dict:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{metodo}"
    r = httpx.post(url, json=dados, timeout=TIMEOUT)
    corpo = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or not corpo.get("ok"):
        raise ErroEnvio(f"Telegram {metodo}: {corpo.get('description') or r.status_code}")
    return corpo.get("result") or {}


def enviar_telegram(chat_id: str, texto: str) -> None:
    _tg("sendMessage", chat_id=chat_id, text=texto)


def configurar_webhook_telegram(url: str) -> None:
    dados = {"url": url, "allowed_updates": ["message"]}
    if settings.TELEGRAM_WEBHOOK_SECRET:
        dados["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET
    _tg("setWebhook", **dados)


def _assinatura(usuario_id: int) -> str:
    chave = settings.SECRET_KEY.encode()
    return hmac.new(chave, f"tg:{usuario_id}".encode(), hashlib.sha256).hexdigest()[:20]


def codigo_vinculo(usuario_id: int) -> str:
    """Código do link t.me/<bot>?start=<código> (o Telegram aceita só [A-Za-z0-9_-])."""
    return f"{usuario_id}_{_assinatura(usuario_id)}"


def usuario_do_codigo(codigo: str) -> int | None:
    m = re.fullmatch(r"(\d+)_([0-9a-f]{20})", codigo or "")
    if not m:
        return None
    uid = int(m.group(1))
    return uid if hmac.compare_digest(m.group(2), _assinatura(uid)) else None


def link_vinculo(usuario_id: int) -> str | None:
    if not settings.TELEGRAM_BOT_USERNAME:
        return None
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME.lstrip('@')}?start={codigo_vinculo(usuario_id)}"


# ------------------------------------------------------------------ WhatsApp ---
def whatsapp_ativo() -> bool:
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def numero_whatsapp(telefone: str) -> str:
    """'(34) 99999-0002' -> '5534999990002' (inclui o 55 quando falta o DDI)."""
    dig = re.sub(r"\D", "", telefone or "")
    if len(dig) in (10, 11):  # DDD + número, sem DDI
        dig = "55" + dig
    return dig


def enviar_whatsapp(telefone: str, texto: str) -> None:
    """
    Sem WHATSAPP_TEMPLATE manda texto livre — o WhatsApp só entrega se o cliente
    falou com o número nas últimas 24h (ou se for o número de teste da Meta).
    Com WHATSAPP_TEMPLATE manda um template aprovado cujo corpo tem UMA variável
    {{1}}, preenchida com a mensagem — funciona a qualquer momento.
    """
    url = (f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
           f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
    dados = {"messaging_product": "whatsapp", "to": numero_whatsapp(telefone)}
    if settings.WHATSAPP_TEMPLATE:
        dados |= {"type": "template", "template": {
            "name": settings.WHATSAPP_TEMPLATE,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANG},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": texto[:1000]}]}],
        }}
    else:
        dados |= {"type": "text", "text": {"body": texto}}
    r = httpx.post(url, json=dados, timeout=TIMEOUT,
                   headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"})
    if r.status_code >= 300:
        try:
            msg = r.json().get("error", {}).get("message")
        except ValueError:
            msg = None
        raise ErroEnvio(f"WhatsApp: {msg or r.status_code}")
