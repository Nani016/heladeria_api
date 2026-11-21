from conftest import PASS_ADMIN


def test_login_correcto_devuelve_token(client):
    r = client.post("/auth/login", json={"username": "admin", "password": PASS_ADMIN})
    assert r.status_code == 200
    body = r.get_json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["usuario"]["rol"] == "admin"
    assert "password" not in str(body).lower().replace("password_hash", "")


def test_login_password_incorrecta(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_login_usuario_inexistente_mismo_mensaje(client):
    """No debe revelar si el usuario existe o no."""
    r1 = client.post("/auth/login", json={"username": "admin", "password": "incorrecta"})
    r2 = client.post("/auth/login", json={"username": "noexiste", "password": "incorrecta"})
    assert r1.status_code == r2.status_code == 401
    assert r1.get_json() == r2.get_json()


def test_login_sin_cuerpo(client):
    assert client.post("/auth/login").status_code in (400, 415)


def test_login_tipos_invalidos(client):
    r = client.post("/auth/login", json={"username": 123, "password": ["x"]})
    assert r.status_code == 400


def test_perfil_con_token(client, h_admin):
    r = client.get("/auth/perfil", headers=h_admin)
    assert r.status_code == 200
    assert r.get_json()["username"] == "admin"


def test_perfil_sin_token(client):
    assert client.get("/auth/perfil").status_code == 401


def test_token_falso_rechazado(client):
    r = client.get("/auth/perfil", headers={"Authorization": "Bearer esto.no.esvalido"})
    assert r.status_code == 401


def test_logout_revoca_el_token(client, h_empleado):
    assert client.get("/auth/perfil", headers=h_empleado).status_code == 200
    assert client.post("/auth/logout", headers=h_empleado).status_code == 200
    r = client.get("/auth/perfil", headers=h_empleado)
    assert r.status_code == 401


def test_registro_solo_admin(client, h_empleado, h_admin):
    nuevo = {"username": "nuevo.user", "password": "ClaveSegura123", "rol": "empleado"}
    assert client.post("/auth/registro", json=nuevo, headers=h_empleado).status_code == 403
    assert client.post("/auth/registro", json=nuevo).status_code == 401
    r = client.post("/auth/registro", json=nuevo, headers=h_admin)
    assert r.status_code == 201
    assert "password" not in r.get_json()["usuario"]


def test_registro_usuario_duplicado(client, h_admin):
    r = client.post(
        "/auth/registro",
        json={"username": "admin", "password": "ClaveSegura123"},
        headers=h_admin,
    )
    assert r.status_code == 409


def test_registro_password_debil(client, h_admin):
    r = client.post(
        "/auth/registro",
        json={"username": "debil", "password": "corta"},
        headers=h_admin,
    )
    assert r.status_code == 400
    assert "password" in r.get_json()["detalles"]


def test_registro_no_permite_rol_inventado(client, h_admin):
    r = client.post(
        "/auth/registro",
        json={"username": "hacker", "password": "ClaveSegura123", "rol": "superadmin"},
        headers=h_admin,
    )
    assert r.status_code == 400


def test_password_se_guarda_hasheada(app):
    from models import Usuario
    u = Usuario.query.filter_by(username="admin").first()
    assert u.password_hash != PASS_ADMIN
    assert PASS_ADMIN not in u.password_hash
    assert u.check_password(PASS_ADMIN)
