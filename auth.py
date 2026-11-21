from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt, get_jwt_identity, verify_jwt_in_request,
)
from extensions import db, jwt, limiter
from models import Usuario, TokenRevocado
from validators import validar_usuario

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Hash falso para que el login tarde igual exista o no el usuario
# (evita descubrir usuarios válidos midiendo tiempos de respuesta).
_HASH_FALSO = Usuario()
_HASH_FALSO.set_password("contraseña-falsa-Xx1234567")


# ----------------------------------------------------------------------
# Callbacks de JWT
# ----------------------------------------------------------------------
@jwt.token_in_blocklist_loader
def token_revocado(_header, payload):
    return db.session.query(TokenRevocado.id).filter_by(jti=payload["jti"]).first() is not None


@jwt.unauthorized_loader
def sin_token(motivo):
    return jsonify({"error": "Autenticación requerida", "detalle": motivo}), 401


@jwt.invalid_token_loader
def token_invalido(motivo):
    return jsonify({"error": "Token inválido"}), 401


@jwt.expired_token_loader
def token_expirado(_header, _payload):
    return jsonify({"error": "El token expiró, inicie sesión de nuevo"}), 401


@jwt.revoked_token_loader
def token_revocado_cb(_header, _payload):
    return jsonify({"error": "El token fue revocado (sesión cerrada)"}), 401


# ----------------------------------------------------------------------
# Decorador de roles
# ----------------------------------------------------------------------
def rol_requerido(*roles):
    def decorador(fn):
        @wraps(fn)
        def envoltura(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get("rol") not in roles:
                return jsonify({"error": "No tiene permisos para esta acción"}), 403
            return fn(*args, **kwargs)
        return envoltura
    return decorador


# ----------------------------------------------------------------------
# POST /auth/login
# ----------------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Se esperaba un cuerpo JSON"}), 400

    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username y password son obligatorios"}), 400

    usuario = Usuario.query.filter_by(username=username.strip()).first()
    if usuario is None:
        _HASH_FALSO.check_password(password)
        valido = False
    else:
        valido = usuario.check_password(password) and usuario.activo

    if not valido:
        # Mensaje genérico: no revela si el usuario existe
        return jsonify({"error": "Credenciales incorrectas"}), 401

    token = create_access_token(identity=str(usuario.id), additional_claims={"rol": usuario.rol})
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expira_en_segundos": int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        "usuario": usuario.to_dict(),
    }), 200


# ----------------------------------------------------------------------
# POST /auth/logout  -> revoca el token actual
# ----------------------------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    db.session.add(TokenRevocado(jti=get_jwt()["jti"]))
    db.session.commit()
    return jsonify({"mensaje": "Sesión cerrada correctamente"}), 200


# ----------------------------------------------------------------------
# GET /auth/perfil
# ----------------------------------------------------------------------
@auth_bp.route("/perfil", methods=["GET"])
@jwt_required()
def perfil():
    usuario = db.session.get(Usuario, int(get_jwt_identity()))
    if usuario is None or not usuario.activo:
        return jsonify({"error": "Usuario no disponible"}), 401
    return jsonify(usuario.to_dict()), 200


# ----------------------------------------------------------------------
# POST /auth/registro  -> solo un admin puede crear usuarios
# ----------------------------------------------------------------------
@auth_bp.route("/registro", methods=["POST"])
@rol_requerido("admin")
def registro():
    limpio, errores = validar_usuario(request.get_json(silent=True))
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

    if Usuario.query.filter_by(username=limpio["username"]).first():
        return jsonify({"error": "Ese nombre de usuario ya existe"}), 409

    usuario = Usuario(username=limpio["username"], rol=limpio["rol"])
    usuario.set_password(limpio["password"])
    db.session.add(usuario)
    db.session.commit()
    return jsonify({"mensaje": "Usuario creado correctamente", "usuario": usuario.to_dict()}), 201
