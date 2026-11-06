"""Histórico de notificações, disparo de lembretes e canais (Telegram / WhatsApp)."""
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app import mensageiros, models, notificacoes
from app.config import settings
from app.database import get_db
from app.deps import somente_admin, usuario_atual
from app import schemas

log = logging.getLogger("barberiq.telegram")
router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("/minhas", response_model=list[schemas.NotificacaoOut], summary="Notificações do usuário logado")
def minhas(limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db),
           usuario: models.Usuario = Depends(usuario_atual)):
    return (db.query(models.Notificacao).filter(models.Notificacao.usuario_id == usuario.id)
            .order_by(models.Notificacao.id.desc()).limit(limit).all())


@router.get("", response_model=list[schemas.NotificacaoOut], dependencies=[Depends(somente_admin)],
            summary="Todas as notificações (admin)")
def todas(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(models.Notificacao).order_by(models.Notificacao.id.desc()).limit(limit).all()


@router.post("/disparar-lembretes", dependencies=[Depends(somente_admin)],
             summary="Envia agora os lembretes pendentes (24h normal / 48h reforçado p/ alto risco)")
def disparar(db: Session = Depends(get_db)):
    return {"enviados": notificacoes.disparar_lembretes(db)}


# ------------------------------------------------------------------ canais ---
@router.get("/canais", response_model=schemas.CanaisOut, summary="Canais de mensagem do usuário logado")
def canais(usuario: models.Usuario = Depends(usuario_atual)):
    return schemas.CanaisOut(
        canal_atual=notificacoes.canal_padrao(usuario),
        telegram_ativo=mensageiros.telegram_ativo(),
        telegram_vinculado=bool(usuario.telegram_chat_id),
        telegram_link=mensageiros.link_vinculo(usuario.id) if mensageiros.telegram_ativo() else None,
        whatsapp_ativo=mensageiros.whatsapp_ativo(),
        telefone=usuario.telefone,
    )


@router.delete("/telegram", status_code=204, summary="Desvincula o Telegram do usuário logado")
def desvincular(db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    usuario.telegram_chat_id = None
    db.commit()


@router.post("/teste", response_model=schemas.NotificacaoOut,
             summary="Envia uma mensagem de teste para o usuário logado (pelo canal atual)")
def teste(db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    return notificacoes.notificar(
        db, usuario, models.TipoNotificacao.confirmacao,
        f"Olá, {usuario.nome}! 💈 Mensagem de teste do AI Barbershop: suas confirmações chegarão por aqui.",
    )


@router.post("/telegram/configurar-webhook", dependencies=[Depends(somente_admin)],
             summary="Registra no Telegram a URL do webhook desta API (rode 1x após o deploy)")
def configurar_webhook(request: Request):
    if not mensageiros.telegram_ativo():
        raise HTTPException(400, "Defina TELEGRAM_BOT_TOKEN na API antes de configurar o webhook.")
    base = str(request.base_url).rstrip("/")
    if not base.startswith(("http://localhost", "http://127.0.0.1")):
        base = "https://" + base.split("://", 1)[1]  # Render/Vercel ficam atrás de proxy HTTPS
    url = f"{base}/notificacoes/telegram/webhook"
    try:
        mensageiros.configurar_webhook_telegram(url)
    except mensageiros.ErroEnvio as e:
        raise HTTPException(502, str(e))
    return {"webhook": url}


@router.post("/telegram/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db),
                  x_telegram_bot_api_secret_token: str | None = Header(None)):
    """Recebe as mensagens do bot. '/start <código>' vincula o chat ao usuário."""
    segredo = settings.TELEGRAM_WEBHOOK_SECRET
    if segredo and not hmac.compare_digest(x_telegram_bot_api_secret_token or "", segredo):
        raise HTTPException(403, "Segredo do webhook inválido.")
    try:
        update = await request.json()
    except ValueError:
        return {"ok": True}
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id") or "")
    texto = (msg.get("text") or "").strip()
    if not chat_id or not texto:
        return {"ok": True}

    resposta = _responder(db, chat_id, texto)
    try:
        mensageiros.enviar_telegram(chat_id, resposta)
    except Exception:
        log.exception("Falha ao responder no Telegram")
    return {"ok": True}  # sempre 200: senão o Telegram reenvia a mesma mensagem


def _responder(db: Session, chat_id: str, texto: str) -> str:
    if texto.startswith("/start"):
        partes = texto.split(maxsplit=1)
        uid = mensageiros.usuario_do_codigo(partes[1]) if len(partes) > 1 else None
        usuario = db.get(models.Usuario, uid) if uid else None
        if not usuario:
            return ("Olá! Para receber suas confirmações aqui, abra o AI Barbershop, vá em "
                    "\"Meus agendamentos\" e toque em \"Conectar Telegram\".")
        # um chat pertence a um usuário só
        db.query(models.Usuario).filter(models.Usuario.telegram_chat_id == chat_id,
                                        models.Usuario.id != usuario.id).update({"telegram_chat_id": None})
        usuario.telegram_chat_id = chat_id
        db.commit()
        return (f"Pronto, {usuario.nome}! ✅ Seu Telegram está conectado. Confirmações e lembretes "
                "dos seus agendamentos chegarão por aqui.")
    vinculado = db.query(models.Usuario).filter(models.Usuario.telegram_chat_id == chat_id).first()
    if vinculado:
        return "Recebido, obrigado! 💈 Para marcar, remarcar ou cancelar, use o app AI Barbershop."
    return "Este chat ainda não está conectado. Use o botão \"Conectar Telegram\" no app AI Barbershop."
