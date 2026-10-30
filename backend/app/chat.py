"""
Assistente de agendamento (chatbot) com IA.

O modelo de linguagem (Claude, da Anthropic) entende o pedido do cliente em texto livre
e usa "ferramentas" que chamam as MESMAS regras de negócio da API (horários livres,
criação e cancelamento de agendamento). Ele nunca acessa o banco diretamente e só age
em nome do cliente logado — por isso não enxerga o risco de no-show nem dados de outros.

Sem ANTHROPIC_API_KEY configurada, /chat/status informa ia=false e o front-end usa o
modo guiado (botões), que funciona só com as rotas já existentes.
"""
import json
import logging
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app import agenda, crud, models, notificacoes, tempo
from app.config import settings

log = logging.getLogger("barberiq.chat")
SA = models.StatusAgendamento
MAX_PASSOS = 8  # limite de idas e vindas modelo ↔ ferramentas por mensagem

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

FERRAMENTAS = [
    {
        "name": "listar_servicos",
        "description": "Lista os serviços ativos da barbearia, com id, nome, duração em minutos e preço em reais.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "listar_barbeiros",
        "description": "Lista os barbeiros ativos, com id e nome.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "horarios_livres",
        "description": "Horários em que um barbeiro pode atender um serviço em um dia. "
                       "Só oferece horários futuros, dentro da jornada e sem conflito.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico_id": {"type": "integer"},
                "barbeiro_id": {"type": "integer"},
                "data": {"type": "string", "description": "Dia no formato AAAA-MM-DD"},
            },
            "required": ["servico_id", "barbeiro_id", "data"],
        },
    },
    {
        "name": "criar_agendamento",
        "description": "Cria o agendamento para o cliente logado. Só chame DEPOIS que o cliente "
                       "confirmar explicitamente serviço, barbeiro, dia e horário.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico_id": {"type": "integer"},
                "barbeiro_id": {"type": "integer"},
                "data_hora": {"type": "string", "description": "Início no formato AAAA-MM-DDTHH:MM"},
            },
            "required": ["servico_id", "barbeiro_id", "data_hora"],
        },
    },
    {
        "name": "meus_agendamentos",
        "description": "Lista os próximos agendamentos confirmados do cliente logado, com id.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancelar_agendamento",
        "description": "Cancela um agendamento futuro do cliente logado. Só chame DEPOIS que o "
                       "cliente confirmar explicitamente qual agendamento quer cancelar.",
        "input_schema": {
            "type": "object",
            "properties": {"agendamento_id": {"type": "integer"}},
            "required": ["agendamento_id"],
        },
    },
]


def _instrucoes(cliente: models.Usuario) -> str:
    agora = tempo.agora()
    return (
        "Você é o assistente virtual da barbearia AI Barbershop e conversa em português do Brasil, "
        "de forma breve, simpática e objetiva (no máximo 4 frases curtas por resposta).\n"
        f"Agora é {DIAS[agora.weekday()]}, {agora:%d/%m/%Y %H:%M} (horário de Brasília). "
        f"O cliente se chama {cliente.nome.split()[0]}.\n"
        "Você ajuda a: ver serviços e preços, ver barbeiros, consultar horários livres, agendar, "
        "listar e cancelar os agendamentos DESTE cliente. Para outros assuntos, diga com educação "
        "que só ajuda com agendamentos.\n"
        "Regras:\n"
        "- Use SEMPRE as ferramentas para serviços, barbeiros e horários; nunca invente horários, preços ou ids.\n"
        "- Converta datas relativas ('amanhã', 'sábado') para AAAA-MM-DD a partir da data de hoje.\n"
        "- Se o cliente não disser o barbeiro, consulte os horários de cada barbeiro e ofereça opções.\n"
        "- Ao listar horários, mostre no máximo 6 opções.\n"
        "- ANTES de criar ou cancelar, resuma (serviço, barbeiro, dia e hora, preço) e peça um 'sim'. "
        "Só chame criar_agendamento ou cancelar_agendamento depois da confirmação.\n"
        "- Se uma ferramenta devolver 'erro', explique ao cliente em linguagem simples e sugira alternativa.\n"
        "- Datas no formato dd/mm e horas como 14h ou 14h30."
    )


# ----------------------------------------------------------- ferramentas ---
def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _executar(db: Session, cliente: models.Usuario, nome: str, args: dict) -> dict:
    """Executa uma ferramenta com as regras da API. Erros de regra viram {'erro': ...}."""
    try:
        if nome == "listar_servicos":
            return {"servicos": [
                {"id": s.id, "nome": s.nome, "duracao_min": s.duracao_min, "preco": float(s.preco)}
                for s in crud.listar_servicos(db)
            ]}
        if nome == "listar_barbeiros":
            barbeiros = (db.query(models.Usuario)
                         .filter_by(tipo=models.TipoUsuario.barbeiro, ativo=True)
                         .order_by(models.Usuario.nome).all())
            return {"barbeiros": [{"id": b.id, "nome": b.nome} for b in barbeiros]}
        if nome == "horarios_livres":
            servico = crud.obter_servico(db, int(args["servico_id"]))
            if not servico or not servico.ativo:
                return {"erro": "Serviço não encontrado."}
            if not crud.obter_usuario(db, int(args["barbeiro_id"]), models.TipoUsuario.barbeiro):
                return {"erro": "Barbeiro não encontrado."}
            dia = date.fromisoformat(str(args["data"]))
            livres = agenda.horarios_livres(db, int(args["barbeiro_id"]), servico, dia)
            return {"data": dia.isoformat(), "dia_semana": DIAS[dia.weekday()],
                    "horarios": [h.strftime("%H:%M") for h in livres]}
        if nome == "criar_agendamento":
            quando = datetime.fromisoformat(str(args["data_hora"]))
            ag = agenda.criar_agendamento(db, cliente, int(args["barbeiro_id"]), int(args["servico_id"]), quando)
            return {"ok": True, "agendamento_id": ag.id, "data_hora": _fmt(ag.data_hora),
                    "servico": ag.servico.nome, "barbeiro": ag.barbeiro.nome, "preco": float(ag.servico.preco)}
        if nome == "meus_agendamentos":
            ags = (db.query(models.Agendamento)
                   .options(joinedload(models.Agendamento.servico), joinedload(models.Agendamento.barbeiro))
                   .filter(models.Agendamento.cliente_id == cliente.id,
                           models.Agendamento.status == SA.confirmado,
                           models.Agendamento.data_hora > tempo.agora())
                   .order_by(models.Agendamento.data_hora).limit(20).all())
            return {"agendamentos": [
                {"id": a.id, "data_hora": _fmt(a.data_hora), "servico": a.servico.nome, "barbeiro": a.barbeiro.nome}
                for a in ags
            ]}
        if nome == "cancelar_agendamento":
            ag = db.get(models.Agendamento, int(args["agendamento_id"]))
            if not ag or ag.cliente_id != cliente.id:
                return {"erro": "Agendamento não encontrado."}
            if ag.status != SA.confirmado:
                return {"erro": "Só é possível cancelar agendamentos confirmados."}
            if ag.data_hora <= tempo.agora():
                return {"erro": "Este horário já passou e não pode ser cancelado."}
            ag.status = SA.cancelado
            db.commit()
            db.refresh(ag)
            notificacoes.notificar_cancelamento(db, ag)
            return {"ok": True, "agendamento_id": ag.id}
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    except HTTPException as e:
        return {"erro": e.detail}
    except (KeyError, ValueError, TypeError):
        return {"erro": "Dados inválidos. Use datas AAAA-MM-DD e horas AAAA-MM-DDTHH:MM."}


# ---------------------------------------------------------------- modelo ---
def _chamar_modelo(system: str, mensagens: list):
    """Chamada à API da Anthropic (isolada para poder ser simulada nos testes)."""
    import anthropic

    cliente_api = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=40.0, max_retries=1)
    return cliente_api.messages.create(
        model=settings.CHAT_MODEL, max_tokens=800, system=system, tools=FERRAMENTAS, messages=mensagens,
    )


def responder(db: Session, cliente: models.Usuario, historico: list[dict]) -> dict:
    """historico: [{'papel': 'user'|'assistant', 'texto': str}, ...] terminando com o cliente."""
    mensagens = [{"role": m["papel"], "content": m["texto"]} for m in historico]
    system = _instrucoes(cliente)
    atualizou = False

    for _ in range(MAX_PASSOS):
        resp = _chamar_modelo(system, mensagens)
        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text").strip()
            return {"resposta": texto or "Desculpe, não entendi. Pode repetir?", "atualizou": atualizou}

        mensagens.append({"role": "assistant", "content": resp.content})
        resultados = []
        for bloco in resp.content:
            if bloco.type != "tool_use":
                continue
            saida = _executar(db, cliente, bloco.name, dict(bloco.input or {}))
            if bloco.name in ("criar_agendamento", "cancelar_agendamento") and saida.get("ok"):
                atualizou = True
            resultados.append({"type": "tool_result", "tool_use_id": bloco.id,
                               "content": json.dumps(saida, ensure_ascii=False)})
        mensagens.append({"role": "user", "content": resultados})

    return {"resposta": "Desculpe, me enrolei aqui. Pode reformular o pedido?", "atualizou": atualizou}
