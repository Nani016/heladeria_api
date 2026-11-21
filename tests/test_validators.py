import pytest
from datetime import date, timedelta

from validators import (
    validar_pedido, validar_password, validar_usuario, validar_estado,
    parse_fecha, parse_hora,
)


def test_pedido_valido_pasa(pedido_valido):
    limpio, errores = validar_pedido(pedido_valido)
    assert errores == {}
    assert limpio["cantidad"] == 20
    assert limpio["estado"] == "Pendiente"


def test_textos_se_recortan(pedido_valido):
    pedido_valido["cliente"] = "   Ana   "
    limpio, _ = validar_pedido(pedido_valido)
    assert limpio["cliente"] == "Ana"


def test_toppings_es_opcional(pedido_valido):
    del pedido_valido["toppings"]
    limpio, errores = validar_pedido(pedido_valido)
    assert errores == {}
    assert limpio["toppings"] is None


@pytest.mark.parametrize("valor", ["<script>alert(1)</script>", "Ana<b>", "a>b"])
def test_rechaza_html_en_textos(pedido_valido, valor):
    pedido_valido["cliente"] = valor
    _, errores = validar_pedido(pedido_valido)
    assert "cliente" in errores


def test_rechaza_caracteres_de_control(pedido_valido):
    pedido_valido["sabor"] = "Choco\x00late"
    _, errores = validar_pedido(pedido_valido)
    assert "sabor" in errores


def test_rechaza_texto_demasiado_largo(pedido_valido):
    pedido_valido["cliente"] = "A" * 101
    _, errores = validar_pedido(pedido_valido)
    assert "cliente" in errores


@pytest.mark.parametrize("campo,valor", [
    ("cantidad", 0), ("cantidad", -5), ("cantidad", 501),
    ("cantidad", "20"), ("cantidad", 2.5), ("cantidad", True),
    ("tiempo_preparacion", 0), ("tiempo_preparacion", 1441),
])
def test_rechaza_numeros_invalidos(pedido_valido, campo, valor):
    pedido_valido[campo] = valor
    _, errores = validar_pedido(pedido_valido)
    assert campo in errores


def test_rechaza_fecha_en_el_pasado(pedido_valido):
    pedido_valido["fecha_entrega"] = (date.today() - timedelta(days=1)).isoformat()
    _, errores = validar_pedido(pedido_valido)
    assert "fecha_entrega" in errores


def test_acepta_fecha_de_hoy(pedido_valido):
    pedido_valido["fecha_entrega"] = date.today().isoformat()
    _, errores = validar_pedido(pedido_valido)
    assert errores == {}


@pytest.mark.parametrize("valor", ["18-09-2026", "2026/09/18", "2026-13-40", "mañana", 20260918, None])
def test_rechaza_formatos_de_fecha(pedido_valido, valor):
    pedido_valido["fecha_entrega"] = valor
    _, errores = validar_pedido(pedido_valido)
    assert "fecha_entrega" in errores


@pytest.mark.parametrize("valor", ["25:00", "abc", "16:60", 1600, None])
def test_rechaza_horas_invalidas(pedido_valido, valor):
    pedido_valido["hora_entrega"] = valor
    _, errores = validar_pedido(pedido_valido)
    assert "hora_entrega" in errores


def test_parse_hora_formatos():
    assert parse_hora("16:00").hour == 16
    assert parse_hora("4:00 PM").hour == 16
    assert parse_hora("4:00 pm").hour == 16
    assert parse_hora("12:00 AM").hour == 0


def test_parse_fecha():
    assert parse_fecha("2026-09-18") == date(2026, 9, 18)
    assert parse_fecha("basura") is None


def test_cuerpo_que_no_es_objeto():
    for malo in (None, [], "texto", 5):
        limpio, errores = validar_pedido(malo)
        assert limpio is None and "cuerpo" in errores


def test_estado_invalido_en_pedido(pedido_valido):
    pedido_valido["estado"] = "Inventado"
    _, errores = validar_pedido(pedido_valido)
    assert "estado" in errores


def test_validar_estado():
    assert validar_estado({"estado": "Listo"}) == ("Listo", {})
    assert validar_estado({"estado": "x"})[0] is None
    assert validar_estado(None)[0] is None


@pytest.mark.parametrize("password,valida", [
    ("ClaveSegura123", True),
    ("corta1A", False),            # menos de 10
    ("todaminuscula123", False),   # sin mayúscula
    ("TODAMAYUSCULA123", False),   # sin minúscula
    ("SinNumerosAqui", False),     # sin número
    ("A1a" * 50, False),           # demasiado larga
    (12345678901, False),          # no es texto
])
def test_politica_de_passwords(password, valida):
    assert (validar_password(password) is None) is valida


@pytest.mark.parametrize("username", ["ab", "con espacio", "raro;--", "a" * 51, "' OR 1=1 --", ""])
def test_username_invalido(username):
    _, errores = validar_usuario({"username": username, "password": "ClaveSegura123"})
    assert "username" in errores
