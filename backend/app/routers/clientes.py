"""
CRUD de clientes (admin) — base: /clientes
Barbeiros também podem consultar (listar/obter) para atender.
"""
from app import models
from app.deps import admin_ou_barbeiro
from app.routers.usuarios_base import criar_router

router = criar_router("/clientes", "Clientes", models.TipoUsuario.cliente, "Cliente", leitura=admin_ou_barbeiro)
