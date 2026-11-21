from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Pedido, ESTADOS_FINALES
from validators import validar_pedido, validar_estado, parse_fecha
from auth import rol_requerido

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


def _no_encontrado():
    return jsonify({"error": "Pedido no encontrado"}), 404


def _invalido(errores):
    return jsonify({"error": "Datos inválidos", "detalles": errores}), 400


# ---------------------------------------------------------------------
# POST /pedidos  -> registrar un nuevo pedido
# ---------------------------------------------------------------------
@pedidos_bp.route("", methods=["POST"])
@jwt_required()
def crear_pedido():
    limpio, errores = validar_pedido(request.get_json(silent=True))
    if errores:
        return _invalido(errores)

    pedido = Pedido(**limpio, creado_por=int(get_jwt_identity()))
    db.session.add(pedido)
    db.session.commit()
    return jsonify({"mensaje": "Pedido registrado correctamente", "pedido": pedido.to_dict()}), 201


# ---------------------------------------------------------------------
# GET /pedidos  -> listar (con paginación y filtro opcional por estado)
# ---------------------------------------------------------------------
@pedidos_bp.route("", methods=["GET"])
@jwt_required()
def listar_pedidos():
    pagina = max(request.args.get("pagina", default=1, type=int) or 1, 1)
    por_pagina = request.args.get("por_pagina", default=20, type=int) or 20
    por_pagina = min(max(por_pagina, 1), 100)

    consulta = Pedido.query
    estado = request.args.get("estado")
    if estado:
        consulta = consulta.filter(Pedido.estado == estado)

    paginacion = consulta.order_by(Pedido.fecha_entrega, Pedido.hora_entrega).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )
    return jsonify({
        "pagina": paginacion.page,
        "por_pagina": por_pagina,
        "total": paginacion.total,
        "paginas": paginacion.pages,
        "pedidos": [p.to_dict() for p in paginacion.items],
    }), 200


# ---------------------------------------------------------------------
# GET /pedidos/fecha/<fecha>  -> pedidos de una fecha
# ---------------------------------------------------------------------
@pedidos_bp.route("/fecha/<fecha>", methods=["GET"])
@jwt_required()
def pedidos_por_fecha(fecha):
    fecha_parseada = parse_fecha(fecha)
    if fecha_parseada is None:
        return jsonify({"error": "Formato de fecha inválido, use YYYY-MM-DD"}), 400

    pedidos = (
        Pedido.query.filter_by(fecha_entrega=fecha_parseada)
        .order_by(Pedido.hora_entrega)
        .all()
    )
    return jsonify({
        "fecha": fecha_parseada.isoformat(),
        "total_pedidos": len(pedidos),
        "minutos_totales_preparacion": sum(p.tiempo_preparacion for p in pedidos),
        "pedidos": [p.to_dict() for p in pedidos],
    }), 200


# ---------------------------------------------------------------------
# GET /pedidos/proximos  -> pedidos activos que se entregan pronto
# ---------------------------------------------------------------------
@pedidos_bp.route("/proximos", methods=["GET"])
@jwt_required()
def pedidos_proximos():
    horas = request.args.get("horas", default=48, type=int)
    if horas is None or not (1 <= horas <= 720):
        return jsonify({"error": "El parámetro 'horas' debe estar entre 1 y 720"}), 400

    ahora = datetime.now()
    limite = ahora + timedelta(hours=horas)

    candidatos = (
        Pedido.query.filter(
            Pedido.estado.notin_(ESTADOS_FINALES),
            Pedido.fecha_entrega >= ahora.date(),
            Pedido.fecha_entrega <= limite.date(),
        )
        .order_by(Pedido.fecha_entrega, Pedido.hora_entrega)
        .all()
    )
    proximos = [
        p for p in candidatos
        if ahora <= datetime.combine(p.fecha_entrega, p.hora_entrega) <= limite
    ]
    return jsonify({
        "horas": horas,
        "total": len(proximos),
        "pedidos": [p.to_dict() for p in proximos],
    }), 200


# ---------------------------------------------------------------------
# GET /pedidos/<id>
# ---------------------------------------------------------------------
@pedidos_bp.route("/<int:pedido_id>", methods=["GET"])
@jwt_required()
def obtener_pedido(pedido_id):
    pedido = db.session.get(Pedido, pedido_id)
    if pedido is None:
        return _no_encontrado()
    return jsonify(pedido.to_dict()), 200


# ---------------------------------------------------------------------
# PUT /pedidos/<id>  -> actualización completa
# ---------------------------------------------------------------------
@pedidos_bp.route("/<int:pedido_id>", methods=["PUT"])
@jwt_required()
def actualizar_pedido(pedido_id):
    pedido = db.session.get(Pedido, pedido_id)
    if pedido is None:
        return _no_encontrado()
    if pedido.estado in ESTADOS_FINALES:
        return jsonify({"error": f"No se puede modificar un pedido {pedido.estado.lower()}"}), 409

    limpio, errores = validar_pedido(request.get_json(silent=True), estado_por_defecto=pedido.estado)
    if errores:
        return _invalido(errores)

    for campo, valor in limpio.items():
        setattr(pedido, campo, valor)
    db.session.commit()
    return jsonify({"mensaje": "Pedido actualizado correctamente", "pedido": pedido.to_dict()}), 200


# ---------------------------------------------------------------------
# PATCH /pedidos/<id>/estado  -> solo el estado
# ---------------------------------------------------------------------
@pedidos_bp.route("/<int:pedido_id>/estado", methods=["PATCH"])
@jwt_required()
def actualizar_estado(pedido_id):
    pedido = db.session.get(Pedido, pedido_id)
    if pedido is None:
        return _no_encontrado()

    nuevo_estado, errores = validar_estado(request.get_json(silent=True))
    if errores:
        return _invalido(errores)

    if pedido.estado in ESTADOS_FINALES:
        return jsonify({"error": f"El pedido ya está {pedido.estado.lower()} y no puede cambiar de estado"}), 409

    pedido.estado = nuevo_estado
    db.session.commit()
    return jsonify({"mensaje": "Estado actualizado correctamente", "pedido": pedido.to_dict()}), 200


# ---------------------------------------------------------------------
# DELETE /pedidos/<id>  -> solo administradores
# ---------------------------------------------------------------------
@pedidos_bp.route("/<int:pedido_id>", methods=["DELETE"])
@rol_requerido("admin")
def eliminar_pedido(pedido_id):
    pedido = db.session.get(Pedido, pedido_id)
    if pedido is None:
        return _no_encontrado()
    db.session.delete(pedido)
    db.session.commit()
    return jsonify({"mensaje": f"Pedido {pedido_id} eliminado correctamente"}), 200
