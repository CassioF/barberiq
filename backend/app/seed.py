"""
Popula o banco com dados de demonstração (idempotente: não duplica).

    python -m app.seed

Contas de teste (senha entre parênteses):
    admin@barberiq.com (admin123) · carlos@barberiq.com / rafael@barberiq.com / diego@barberiq.com (barbeiro123)
    maria@email.com e outros clientes (cliente123)
"""
import random
from datetime import datetime, time, timedelta

from app import models, tempo
from app.agenda import calcular_risco
from app.database import Base, SessionLocal, engine
from app.ia import noshow
from app.security import hash_senha

SA = models.StatusAgendamento
random.seed(7)

BARBEIROS = [("Carlos Mendes", "carlos@barberiq.com", "34999990011"),
             ("Rafael Souza", "rafael@barberiq.com", "34999990012"),
             ("Diego Lima", "diego@barberiq.com", "34999990013")]
SERVICOS = [("Corte", "Corte masculino na tesoura ou máquina", 30, 45),
            ("Barba", "Barba com toalha quente", 30, 35),
            ("Corte + Barba", "Combo completo", 60, 75),
            ("Sobrancelha", "Design de sobrancelha", 30, 20)]
CLIENTES = ["Maria Silva", "João Pereira", "Lucas Almeida", "Ana Costa", "Pedro Rocha", "Bruno Martins",
            "Felipe Santos", "Gabriel Oliveira", "Thiago Ribeiro", "Mateus Carvalho", "Rodrigo Ferreira",
            "André Barbosa", "Camila Nunes", "Vinícius Araújo"]


def _usuario(db, nome, email, tipo, senha, telefone=None):
    u = db.query(models.Usuario).filter_by(email=email).first()
    if not u:
        u = models.Usuario(nome=nome, email=email, tipo=tipo, senha_hash=hash_senha(senha), telefone=telefone)
        db.add(u)
        db.flush()
    return u


def popular():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _usuario(db, "Administrador", "admin@barberiq.com", models.TipoUsuario.admin, "admin123")
        barbeiros = [_usuario(db, n, e, models.TipoUsuario.barbeiro, "barbeiro123", t) for n, e, t in BARBEIROS]
        clientes = []
        for i, nome in enumerate(CLIENTES):
            email = nome.split()[0].lower().replace("í", "i").replace("é", "e") + "@email.com"
            clientes.append(_usuario(db, nome, email, models.TipoUsuario.cliente, "cliente123", f"3499999{i:04d}"))
        for nome, desc, dur, preco in SERVICOS:
            if not db.query(models.Servico).filter_by(nome=nome).first():
                db.add(models.Servico(nome=nome, descricao=desc, duracao_min=dur, preco=preco))
        db.flush()
        for b in barbeiros:
            if not db.query(models.DisponibilidadeBarbeiro).filter_by(barbeiro_id=b.id).first():
                for dia in range(5):  # segunda a sexta
                    db.add(models.DisponibilidadeBarbeiro(barbeiro_id=b.id, dia_semana=dia, hora_inicio=time(9), hora_fim=time(12)))
                    db.add(models.DisponibilidadeBarbeiro(barbeiro_id=b.id, dia_semana=dia, hora_inicio=time(13), hora_fim=time(19)))
                db.add(models.DisponibilidadeBarbeiro(barbeiro_id=b.id, dia_semana=5, hora_inicio=time(9), hora_fim=time(15)))
        db.commit()

        if db.query(models.Agendamento).count():
            print("Agendamentos já existem — histórico não recriado.")
            return
        servicos = db.query(models.Servico).all()
        propensao = {c.id: random.choice([0.02, 0.05, 0.1, 0.4]) for c in clientes}
        agora = tempo.agora()
        ocupado: set = set()
        criados = []
        for delta in range(-60, 8):
            dia = (agora + timedelta(days=delta)).date()
            for b in barbeiros:
                janelas = db.query(models.DisponibilidadeBarbeiro).filter_by(barbeiro_id=b.id, dia_semana=dia.weekday()).all()
                for j in janelas:
                    t = datetime.combine(dia, j.hora_inicio)
                    while t < datetime.combine(dia, j.hora_fim):
                        s = random.choice(servicos)
                        slots = s.duracao_min // 30
                        precisa = [t + timedelta(minutes=30 * k) for k in range(slots)]
                        cabe = t + timedelta(minutes=s.duracao_min) <= datetime.combine(dia, j.hora_fim)
                        if cabe and random.random() < (0.55 if delta < 0 else 0.3) and not any((b.id, x) in ocupado for x in precisa):
                            c = random.choice(clientes)
                            if t > agora:
                                st = SA.confirmado
                            else:
                                st = SA.faltou if random.random() < propensao[c.id] else SA.concluido
                            ag = models.Agendamento(cliente_id=c.id, barbeiro_id=b.id, servico_id=s.id, data_hora=t, status=st)
                            db.add(ag)
                            ocupado.update((b.id, x) for x in precisa)
                            criados.append(ag)
                        t += timedelta(minutes=30)
        db.flush()
        # cliente não pode ter dois atendimentos simultâneos: descarta duplicados do histórico simulado
        vistos, removidos = set(), 0
        for ag in sorted(criados, key=lambda a: a.data_hora):
            chave = (ag.cliente_id, ag.data_hora)
            if chave in vistos:
                db.delete(ag)
                removidos += 1
            else:
                vistos.add(chave)
        db.commit()

        # risco de no-show dos agendamentos futuros (usa o histórico do cliente)
        for ag in db.query(models.Agendamento).filter(models.Agendamento.status == SA.confirmado).all():
            ant = max((ag.data_hora - (ag.data_hora - timedelta(hours=random.randint(2, 96)))).total_seconds() / 3600, 0)
            r = calcular_risco(db, ag.cliente_id, ag.data_hora, ag.data_hora - timedelta(hours=ant))
            db.add(models.PrevisaoNoShow(agendamento_id=ag.id, risco=round(r, 4), modelo_versao=noshow.VERSAO))
        db.commit()
        print(f"Seed concluído: {db.query(models.Agendamento).count()} agendamentos.")


if __name__ == "__main__":
    popular()
