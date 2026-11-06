"""
Envio real de mensagens pelo WhatsApp (Meta Cloud API).

Só é usado quando WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID estão preenchidos;
sem eles, o envio continua SIMULADO (log) — assim a demo e os testes funcionam
sem nenhuma conta externa.
"""
import logging
import re

import httpx

from app.config import settings

log = logging.getLogger("barberiq.whatsapp")
TIMEOUT = httpx.Timeout(10.0)


class ErroEnvio(Exception):
    """O WhatsApp recusou a mensagem (token inválido, número sem WhatsApp...)."""


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
