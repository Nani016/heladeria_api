"""
Validación y sanitización de entradas.

Todo dato que llega del cliente pasa por aquí antes de tocar la base de
datos. Devuelve (datos_limpios, errores).
"""
import re
from datetime import datetime, date

from models import ESTADOS_VALIDOS, ROLES_VALIDOS

# Caracteres de control y símbolos usados en inyección de HTML/scripts
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PELIGROSOS = re.compile(r"[<>]")
_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


def _texto(data, campo, max_len, requerido=True, errores=None):
    valor = data.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if requerido:
            errores[campo] = "Campo obligatorio"
        return None
    if not isinstance(valor, str):
        errores[campo] = "Debe ser texto"
        return None
    valor = valor.strip()
    if _CONTROL.search(valor):
        errores[campo] = "Contiene caracteres no permitidos"
        return None
    if _PELIGROSOS.search(valor):
        errores[campo] = "No se permiten los caracteres < y >"
        return None
    if len(valor) > max_len:
        errores[campo] = f"Máximo {max_len} caracteres"
        return None
    return valor


def _entero(data, campo, minimo, maximo, errores):
    valor = data.get(campo)
    if valor is None:
        errores[campo] = "Campo obligatorio"
        return None
    # bool es subclase de int en Python: se rechaza explícitamente
    if isinstance(valor, bool) or not isinstance(valor, int):
        errores[campo] = "Debe ser un número entero"
        return None
    if not (minimo <= valor <= maximo):
        errores[campo] = f"Debe estar entre {minimo} y {maximo}"
        return None
    return valor


def parse_fecha(valor):
    if not isinstance(valor, str):
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_hora(valor):
    if not isinstance(valor, str):
        return None
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(valor.strip().upper(), fmt).time()
        except ValueError:
            continue
    return None


def validar_pedido(data, estado_por_defecto="Pendiente"):
    """Valida el cuerpo de POST /pedidos y PUT /pedidos/:id."""
    errores = {}
    if not isinstance(data, dict):
        return None, {"cuerpo": "Se esperaba un objeto JSON"}

    limpio = {
        "cliente": _texto(data, "cliente", 100, True, errores),
        "tipo_producto": _texto(data, "tipo_producto", 60, True, errores),
        "sabor": _texto(data, "sabor", 60, True, errores),
        "toppings": _texto(data, "toppings", 120, False, errores),
        "cantidad": _entero(data, "cantidad", 1, 500, errores),
        "tiempo_preparacion": _entero(data, "tiempo_preparacion", 1, 1440, errores),
    }

    fecha = parse_fecha(data.get("fecha_entrega"))
    if fecha is None:
        errores["fecha_entrega"] = "Fecha inválida, use el formato YYYY-MM-DD"
    elif fecha < date.today():
        errores["fecha_entrega"] = "La fecha de entrega no puede estar en el pasado"
    limpio["fecha_entrega"] = fecha

    hora = parse_hora(data.get("hora_entrega"))
    if hora is None:
        errores["hora_entrega"] = "Hora inválida, use HH:MM (24 h) o 'HH:MM AM/PM'"
    limpio["hora_entrega"] = hora

    estado = data.get("estado", estado_por_defecto)
    if estado not in ESTADOS_VALIDOS:
        errores["estado"] = f"Estado inválido. Use: {', '.join(ESTADOS_VALIDOS)}"
    limpio["estado"] = estado

    return (None, errores) if errores else (limpio, {})


def validar_estado(data):
    if not isinstance(data, dict):
        return None, {"cuerpo": "Se esperaba un objeto JSON"}
    estado = data.get("estado")
    if estado not in ESTADOS_VALIDOS:
        return None, {"estado": f"Estado inválido. Use: {', '.join(ESTADOS_VALIDOS)}"}
    return estado, {}


def validar_password(password):
    """Política de contraseñas: 10+ caracteres, mayúscula, minúscula y número."""
    if not isinstance(password, str):
        return "La contraseña debe ser texto"
    if len(password) < 10:
        return "La contraseña debe tener al menos 10 caracteres"
    if len(password) > 128:
        return "La contraseña es demasiado larga (máximo 128)"
    if not re.search(r"[a-z]", password):
        return "La contraseña debe incluir una minúscula"
    if not re.search(r"[A-Z]", password):
        return "La contraseña debe incluir una mayúscula"
    if not re.search(r"\d", password):
        return "La contraseña debe incluir un número"
    return None


def validar_usuario(data):
    errores = {}
    if not isinstance(data, dict):
        return None, {"cuerpo": "Se esperaba un objeto JSON"}

    username = data.get("username")
    if not isinstance(username, str) or not _USERNAME.match(username.strip()):
        errores["username"] = "3 a 50 caracteres: letras, números, punto, guion y guion bajo"

    error_pass = validar_password(data.get("password"))
    if error_pass:
        errores["password"] = error_pass

    rol = data.get("rol", "empleado")
    if rol not in ROLES_VALIDOS:
        errores["rol"] = f"Rol inválido. Use: {', '.join(ROLES_VALIDOS)}"

    if errores:
        return None, errores
    return {"username": username.strip(), "password": data["password"], "rol": rol}, {}
