from datetime import date, timedelta, datetime


def _crear(client, headers, pedido):
    r = client.post("/pedidos", json=pedido, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["pedido"]


# ------------------------- POST /pedidos ------------------------------
def test_crear_pedido(client, h_empleado, pedido_valido):
    r = client.post("/pedidos", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 201
    p = r.get_json()["pedido"]
    assert p["id"] == 1
    assert p["estado"] == "Pendiente"
    assert p["cliente"] == "Kevin Florez"
    assert p["hora_entrega"] == "16:00"


def test_crear_pedido_hora_am_pm(client, h_empleado, pedido_valido):
    pedido_valido["hora_entrega"] = "4:00 PM"
    p = _crear(client, h_empleado, pedido_valido)
    assert p["hora_entrega"] == "16:00"


def test_crear_pedido_requiere_login(client, pedido_valido):
    assert client.post("/pedidos", json=pedido_valido).status_code == 401


def test_crear_pedido_campos_faltantes(client, h_empleado):
    r = client.post("/pedidos", json={"cliente": "Solo nombre"}, headers=h_empleado)
    assert r.status_code == 400
    detalles = r.get_json()["detalles"]
    for campo in ("tipo_producto", "sabor", "cantidad", "fecha_entrega", "hora_entrega", "tiempo_preparacion"):
        assert campo in detalles


def test_crear_pedido_sin_json(client, h_empleado):
    r = client.post("/pedidos", data="no soy json", headers=h_empleado)
    assert r.status_code in (400, 415)


# ----------------------- GET /pedidos ---------------------------------
def test_listar_pedidos_y_paginacion(client, h_empleado, pedido_valido):
    for i in range(5):
        pedido_valido["cliente"] = f"Cliente {i}"
        _crear(client, h_empleado, pedido_valido)
    r = client.get("/pedidos?por_pagina=2&pagina=2", headers=h_empleado)
    body = r.get_json()
    assert r.status_code == 200
    assert body["total"] == 5
    assert body["paginas"] == 3
    assert len(body["pedidos"]) == 2


def test_listar_filtra_por_estado(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    _crear(client, h_empleado, pedido_valido)
    client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "Listo"}, headers=h_empleado)
    body = client.get("/pedidos?estado=Listo", headers=h_empleado).get_json()
    assert body["total"] == 1


def test_listar_requiere_login(client):
    assert client.get("/pedidos").status_code == 401


# --------------------- GET /pedidos/:id --------------------------------
def test_obtener_pedido(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    r = client.get(f"/pedidos/{p['id']}", headers=h_empleado)
    assert r.status_code == 200
    assert r.get_json()["sabor"] == "Chocolate"


def test_obtener_pedido_inexistente(client, h_empleado):
    assert client.get("/pedidos/999", headers=h_empleado).status_code == 404


def test_id_no_numerico_da_404(client, h_empleado):
    assert client.get("/pedidos/abc", headers=h_empleado).status_code == 404


# ------------------- GET /pedidos/fecha/:fecha -------------------------
def test_pedidos_por_fecha(client, h_empleado, pedido_valido, fecha_futura):
    _crear(client, h_empleado, pedido_valido)
    pedido_valido["hora_entrega"] = "10:00"
    pedido_valido["tiempo_preparacion"] = 60
    _crear(client, h_empleado, pedido_valido)
    otro_dia = (date.today() + timedelta(days=20)).isoformat()
    pedido_valido["fecha_entrega"] = otro_dia
    _crear(client, h_empleado, pedido_valido)

    r = client.get(f"/pedidos/fecha/{fecha_futura}", headers=h_empleado)
    body = r.get_json()
    assert r.status_code == 200
    assert body["total_pedidos"] == 2
    assert body["minutos_totales_preparacion"] == 240
    # ordenados por hora
    assert [p["hora_entrega"] for p in body["pedidos"]] == ["10:00", "16:00"]


def test_pedidos_por_fecha_vacia(client, h_empleado):
    body = client.get("/pedidos/fecha/2030-01-01", headers=h_empleado).get_json()
    assert body["total_pedidos"] == 0


def test_pedidos_por_fecha_formato_invalido(client, h_empleado):
    assert client.get("/pedidos/fecha/18-09-2026", headers=h_empleado).status_code == 400


# --------------------- GET /pedidos/proximos ---------------------------
def test_proximos_incluye_solo_activos_dentro_de_ventana(client, h_empleado, pedido_valido):
    manana = (date.today() + timedelta(days=1)).isoformat()
    cercano = dict(pedido_valido, fecha_entrega=manana, hora_entrega="23:59")
    lejano = dict(pedido_valido, fecha_entrega=(date.today() + timedelta(days=30)).isoformat())
    cancelado = _crear(client, h_empleado, dict(cercano, cliente="Cancelado"))
    client.patch(f"/pedidos/{cancelado['id']}/estado", json={"estado": "Cancelado"}, headers=h_empleado)
    _crear(client, h_empleado, cercano)
    _crear(client, h_empleado, lejano)

    body = client.get("/pedidos/proximos?horas=72", headers=h_empleado).get_json()
    assert body["total"] == 1
    assert body["pedidos"][0]["cliente"] == "Kevin Florez"


def test_proximos_parametro_invalido(client, h_empleado):
    assert client.get("/pedidos/proximos?horas=0", headers=h_empleado).status_code == 400
    assert client.get("/pedidos/proximos?horas=99999", headers=h_empleado).status_code == 400


# ---------------------- PUT /pedidos/:id --------------------------------
def test_actualizar_pedido_completo(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    nuevo = dict(pedido_valido, sabor="Fresa", cantidad=30)
    r = client.put(f"/pedidos/{p['id']}", json=nuevo, headers=h_empleado)
    assert r.status_code == 200
    assert r.get_json()["pedido"]["sabor"] == "Fresa"
    assert r.get_json()["pedido"]["cantidad"] == 30


def test_put_exige_todos_los_campos(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    r = client.put(f"/pedidos/{p['id']}", json={"sabor": "Fresa"}, headers=h_empleado)
    assert r.status_code == 400


def test_put_pedido_inexistente(client, h_empleado, pedido_valido):
    assert client.put("/pedidos/999", json=pedido_valido, headers=h_empleado).status_code == 404


def test_no_se_puede_editar_pedido_entregado(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "Entregado"}, headers=h_empleado)
    r = client.put(f"/pedidos/{p['id']}", json=pedido_valido, headers=h_empleado)
    assert r.status_code == 409


# ------------------ PATCH /pedidos/:id/estado --------------------------
def test_cambiar_estado(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    r = client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "En preparación"}, headers=h_empleado)
    assert r.status_code == 200
    assert r.get_json()["pedido"]["estado"] == "En preparación"
    # el resto de campos no cambia
    assert r.get_json()["pedido"]["cliente"] == "Kevin Florez"


def test_estado_invalido(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    r = client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "Volando"}, headers=h_empleado)
    assert r.status_code == 400


def test_estado_final_no_cambia(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "Cancelado"}, headers=h_empleado)
    r = client.patch(f"/pedidos/{p['id']}/estado", json={"estado": "Pendiente"}, headers=h_empleado)
    assert r.status_code == 409


def test_estado_pedido_inexistente(client, h_empleado):
    r = client.patch("/pedidos/999/estado", json={"estado": "Listo"}, headers=h_empleado)
    assert r.status_code == 404


# -------------------- DELETE /pedidos/:id ------------------------------
def test_empleado_no_puede_eliminar(client, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    assert client.delete(f"/pedidos/{p['id']}", headers=h_empleado).status_code == 403
    assert client.get(f"/pedidos/{p['id']}", headers=h_empleado).status_code == 200


def test_admin_elimina_pedido(client, h_admin, h_empleado, pedido_valido):
    p = _crear(client, h_empleado, pedido_valido)
    assert client.delete(f"/pedidos/{p['id']}", headers=h_admin).status_code == 200
    assert client.get(f"/pedidos/{p['id']}", headers=h_admin).status_code == 404


def test_eliminar_sin_login(client):
    assert client.delete("/pedidos/1").status_code == 401


def test_eliminar_inexistente(client, h_admin):
    assert client.delete("/pedidos/999", headers=h_admin).status_code == 404
