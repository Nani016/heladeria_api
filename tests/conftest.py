import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import TestingConfig  # noqa: E402
from extensions import db  # noqa: E402
from models import Usuario  # noqa: E402

PASS_ADMIN = "AdminClave123"
PASS_EMPLEADO = "EmpleadoClave123"


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        for username, password, rol in [
            ("admin", PASS_ADMIN, "admin"),
            ("empleado", PASS_EMPLEADO, "empleado"),
        ]:
            u = Usuario(username=username, rol=rol)
            u.set_password(password)
            db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


@pytest.fixture()
def h_admin(client):
    return _login(client, "admin", PASS_ADMIN)


@pytest.fixture()
def h_empleado(client):
    return _login(client, "empleado", PASS_EMPLEADO)


@pytest.fixture()
def fecha_futura():
    return (date.today() + timedelta(days=10)).isoformat()


@pytest.fixture()
def pedido_valido(fecha_futura):
    return {
        "cliente": "Kevin Florez",
        "tipo_producto": "Torta helada",
        "sabor": "Chocolate",
        "cantidad": 20,
        "toppings": "Chispas de colores",
        "fecha_entrega": fecha_futura,
        "hora_entrega": "16:00",
        "tiempo_preparacion": 180,
    }
