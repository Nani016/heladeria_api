import pytest
from app import create_app
from config import TestingConfig
from extensions import db
from models import Pedido, Usuario


def test_cabeceras_de_seguridad(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" in r.headers


@pytest.mark.parametrize("payload", [
    "'; DROP TABLE pedidos; --",
    "' OR '1'='1",
    "Robert'); DELETE FROM usuarios;--",
])
def test_inyeccion_sql_no_afecta_la_bd(client, h_empleado, pedido_valido, payload):
    """El ORM parametriza las consultas: el texto se guarda tal cual, sin ejecutarse."""
    pedido_valido["cliente"] = payload
    r = client.post("/pedidos", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 201
    assert r.get_json()["pedido"]["cliente"] == payload
    # las tablas siguen intactas
    assert Pedido.query.count() == 1
    assert Usuario.query.count() == 2


def test_inyeccion_sql_en_login(client):
    r = client.post("/auth/login", json={"username": "admin' --", "password": "' OR '1'='1"})
    assert r.status_code == 401


def test_inyeccion_sql_en_url(client, h_empleado):
    assert client.get("/pedidos/fecha/2026-01-01' OR '1'='1", headers=h_empleado).status_code == 400
    assert client.get("/pedidos?estado=' OR 1=1 --", headers=h_empleado).get_json()["total"] == 0


def test_xss_es_rechazado(client, h_empleado, pedido_valido):
    pedido_valido["toppings"] = "<img src=x onerror=alert(1)>"
    r = client.post("/pedidos", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 400
    assert "toppings" in r.get_json()["detalles"]


def test_cuerpo_demasiado_grande_se_rechaza(client, h_empleado, pedido_valido):
    pedido_valido["cliente"] = "A" * 20000
    r = client.post("/pedidos", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 413


def test_no_se_pueden_inyectar_campos_extra(client, h_empleado, pedido_valido):
    """Mass assignment: campos como id, estado de otro usuario o creado_por se ignoran."""
    pedido_valido.update({"id": 999, "creado_por": 12345, "rol": "admin"})
    r = client.post("/pedidos", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 201
    p = Pedido.query.first()
    assert p.id != 999
    assert p.creado_por != 12345


def test_errores_no_filtran_detalles_internos(client, h_empleado):
    r = client.get("/ruta-que-no-existe", headers=h_empleado)
    assert r.status_code == 404
    assert r.get_json() == {"error": "Recurso no encontrado"}
    r = client.post("/", json={})
    assert r.status_code == 405
    assert "Traceback" not in r.get_data(as_text=True)


def test_empleado_no_escala_privilegios_con_token_manipulado(client, h_empleado):
    """Un token alterado (firma inválida) es rechazado."""
    token = h_empleado["Authorization"].split()[1]
    cabecera, payload, firma = token.split(".")
    falso = f"{cabecera}.{payload}.{firma[:-3]}abc"
    r = client.get("/auth/perfil", headers={"Authorization": f"Bearer {falso}"})
    assert r.status_code == 401


def test_usuario_desactivado_no_puede_entrar(app, client):
    u = Usuario.query.filter_by(username="empleado").first()
    u.activo = False
    db.session.commit()
    r = client.post("/auth/login", json={"username": "empleado", "password": "EmpleadoClave123"})
    assert r.status_code == 401


def test_rate_limit_en_login():
    """Tras superar el límite de intentos de login responde 429."""

    class ConLimite(TestingConfig):
        RATELIMIT_ENABLED = True
        LOGIN_RATE_LIMIT = "3 per minute"

    app = create_app(ConLimite)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        codigos = [
            c.post("/auth/login", json={"username": "x", "password": "y"}).status_code
            for _ in range(5)
        ]
        db.session.remove()
        db.drop_all()
    assert codigos[:3] == [401, 401, 401]
    assert codigos[3:] == [429, 429]
