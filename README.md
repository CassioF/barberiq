# BarberShop AI

Plataforma web de agendamento para barbearias com IA para **prever faltas (no-show)**.
Projeto Integrado II · UNIUBE · Sistemas de Informação.

| Camada | Tecnologia |
|---|---|
| Front-end | React 18 + Vite + React Router (responsivo) |
| Back-end | FastAPI (Python) — API REST, JWT, SQLAlchemy |
| Banco | PostgreSQL 16 (7 tabelas — `db/schema_barberiq.sql`) |
| IA | scikit-learn — Regressão Logística treinada com histórico simulado |

```
barberiq/
├── db/schema_barberiq.sql      # criação do banco (enums, UNIQUE, CHECK, JSONB, índices)
├── docker-compose.yml          # PostgreSQL com o schema já aplicado
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI, CORS, lembretes automáticos
│   │   ├── models.py schemas.py crud.py   # (mesmo padrão do CRUD de clientes original)
│   │   ├── agenda.py           # horários livres, conflitos, risco de no-show
│   │   ├── notificacoes.py     # confirmação / lembrete / lembrete reforçado
│   │   ├── mensageiros.py      # envio real pelo WhatsApp (Meta Cloud API)
│   │   ├── security.py deps.py # bcrypt + JWT + permissões por perfil
│   │   ├── ia/noshow.py        # modelo de IA
│   │   ├── routers/            # auth, clientes, barbeiros, servicos, agendamentos, ia, notificacoes, relatorios
│   │   └── seed.py             # dados de demonstração
│   └── tests/                  # pytest
└── frontend/src/pages/         # cliente/ barbeiro/ admin/
```

## Como rodar

**1. Banco** (Docker):
```bash
docker compose up -d db
```
Sem Docker? Crie o banco `barberiq` e rode `psql -h localhost -U postgres -d barberiq -f db/schema_barberiq.sql`.

**2. Back-end**:
```bash
cd backend
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # ajuste a senha/porta se precisar
python -m app.seed                                     # (opcional) dados de demonstração
uvicorn app.main:app --reload
```
Swagger: http://localhost:8000/docs (botão **Authorize** → e-mail e senha).

**3. Front-end**:
```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL=http://localhost:8000
npm run dev               # http://localhost:5173
```

### Contas de demonstração (após `python -m app.seed`)
| Perfil | E-mail | Senha |
|---|---|---|
| Admin | admin@barberiq.com | admin123 |
| Barbeiro | carlos@barberiq.com (também rafael@ e diego@) | barbeiro123 |
| Cliente | maria@email.com (e outros) | cliente123 |

## O que cada perfil faz
- **Cliente** — cadastra-se, escolhe serviço → barbeiro → dia → horário, vê e cancela os próprios agendamentos.
- **Barbeiro** — vê a agenda do dia com o **risco de falta** de cada cliente, marca *concluído* / *não compareceu*, edita seus horários de trabalho.
- **Admin** — painel (faturamento, ticket médio, ocupação, no-show), todos os agendamentos, CRUD de clientes, barbeiros e serviços, simulador da IA, notificações.

## Regras de negócio
- **Sem conflito de horário**: a API só oferece horários dentro da janela do barbeiro, respeitando a duração do serviço e agendamentos existentes; o índice único `(barbeiro_id, data_hora)` no banco é a barreira final contra duas reservas simultâneas. O cliente também não pode ter dois horários sobrepostos.
- **IA de no-show**: ao agendar, a API monta as 3 variáveis (taxa de faltas anteriores do cliente, dia da semana, antecedência em horas), consulta o modelo e grava em `previsao_noshow`. O cliente **não** vê o risco; barbeiro e admin sim (baixo / médio / alto, limite de alto risco = 50%).
- **Lembretes**: 24h antes para risco normal; **48h antes e pedindo confirmação** para alto risco. Disparo automático a cada 15 min (`LEMBRETES_INTERVALO_MIN`) ou pelo botão em *IA & Notificações*.
- **E-mail único**; senha com bcrypt, nunca devolvida; exclusão de usuário/serviço com agendamentos é bloqueada (`409`) — desative-o.
- Perfis: JWT; cada rota valida o perfil (cliente só enxerga os próprios dados).

## Decisões e limites (leia antes da apresentação)
- **UNIQUE parcial**: no slide a restrição é `UNIQUE (barbeiro_id, data_hora)`. Foi implementada como índice único **ignorando cancelados** — senão um horário cancelado nunca poderia ser reaproveitado. O efeito contra duplicidade é o mesmo.
- **Dados da IA são simulados** (como no escopo). Métricas atuais: acurácia ≈ 87%, AUC ≈ 0,66 — o AUC é modesto porque o ruído do gerador é alto; ajuste `gerar_dados_simulados()` em `ia/noshow.py` se quiser, e rode `python -m app.ia.noshow`.
- **O WhatsApp envia de verdade quando configurado** (veja *Mensagens pelo WhatsApp*). Sem configuração, e sempre no e-mail (sem SMTP), o envio é simulado: log + status *enviado*.
- **Tabela `recomendacao_estilo`** existe no banco e nos models, mas não há tela/endpoint: o escopo do MVP lista só a análise de risco de falta como modelo de IA (o consultor visagista ficou como diferencial futuro).
- **Alembic** não foi configurado: o schema vem do `.sql` (ou de `AUTO_CREATE_TABLES=true`, que cria tabelas ausentes pelos models).
- Não há fluxo de "esqueci a senha" nem pagamento (fora do escopo).

## Publicar online (deploy gratuito)

**No ar:** front https://barberiq-pi.vercel.app · API https://barberiq-api.onrender.com/docs

| Parte | Serviço | Configuração |
|---|---|---|
| Banco | **Neon** (ou Supabase) | crie o banco e copie a *connection string* (`postgresql://...?sslmode=require` serve como está) |
| API | **Render** | *New + → Blueprint* → este repositório (usa o `render.yaml`) |
| Front | **Vercel** | *Root Directory* `frontend` · variável `VITE_API_URL=https://<sua-api>.onrender.com` |

1. **Banco**: com `AUTO_CREATE_TABLES=true` a API cria as tabelas sozinha; ou aplique o schema: `psql "<url do Neon>" -f db/schema_barberiq.sql`.
2. **API (Render)**: informe `DATABASE_URL` (Neon) e `CORS_ORIGINS` (URL do Vercel, ex.: `https://barberiq.vercel.app`). O `SECRET_KEY` é gerado automaticamente e o modelo de IA é treinado no build. Com `SEED_DEMO=true` (já no `render.yaml`), a API cria as contas de demonstração sozinha na primeira inicialização com o banco vazio — o plano free do Render não tem *Shell*. Teste em `https://<sua-api>.onrender.com/docs`.
3. **Front (Vercel)**: o `frontend/vercel.json` faz as rotas do React Router (`/admin`, `/agendar`...) funcionarem ao recarregar a página. `VITE_API_URL` é lida no build: se mudar, faça *Redeploy*.

> No plano gratuito o Render "dorme" após inatividade (1ª requisição demora ~1 min) e os lembretes automáticos não rodam enquanto ele dorme. Abra o site antes da apresentação e use o botão manual em *IA & Notificações*.

## Mensagens pelo WhatsApp

Confirmações, lembretes e cancelamentos vão para o WhatsApp do cliente (ou para o e-mail, simulado, se ele não informou número). O cliente informa ou troca o número em *Meus agendamentos* → **Confirmações pelo WhatsApp**, onde também há **Enviar mensagem de teste**. O status (*enviado* / *falha*) aparece em *IA & Notificações*; falha do WhatsApp nunca impede o agendamento. Sem configuração, o envio é simulado.

1. Em developers.facebook.com crie um app do tipo *Business* → produto **WhatsApp** → *API Setup*.
2. Copie o *token* e o *Phone number ID* para `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID` no Render. No número de teste da Meta, cadastre em *To* os celulares que vão receber (até 5).
3. Regra do WhatsApp: mensagem livre só é entregue se o cliente falou com o número nas últimas 24h. Para enviar a qualquer momento, crie e aprove um *template* (categoria *Utility*) com corpo `{{1}}` e informe o nome em `WHATSAPP_TEMPLATE` (idioma em `WHATSAPP_TEMPLATE_LANG`, padrão `pt_BR`).
4. O token temporário expira em 24h; para algo duradouro gere um token permanente de *System User* (Business Settings → System Users).

O telefone é normalizado para o formato internacional (`34999990002` → `5534999990002`).

## Testes
```bash
cd backend && python -m pytest -q        # usa SQLite temporário
# ou contra um PostgreSQL de teste (o conteúdo desse banco é apagado):
TEST_DATABASE_URL=postgresql+psycopg2://postgres:senha123@localhost:5432/barberiq_test python -m pytest -q
```
