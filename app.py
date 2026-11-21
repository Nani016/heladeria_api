import os
import click
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import db, migrate, jwt, limiter


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config.get("TESTING"):
        config_class.validar()

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # CORS: solo los orígenes listados en CORS_ORIGINS (ninguno por defecto)
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=False)

    import models  # noqa: F401  (registra los modelos para las migraciones)
    from auth import auth_bp
    from routes import pedidos_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(pedidos_bp)

    # ------------------------------------------------------------------
    # Cabeceras de seguridad en todas las respuestas
    # ------------------------------------------------------------------
    @app.after_request
    def cabeceras_seguridad(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    @app.route("/")
    def index():
        return jsonify({"mensaje": "API de gestión de pedidos - Heladería", "status": "ok"})

    # ------------------------------------------------------------------
    # Manejo de errores: siempre JSON, sin filtrar detalles internos
    # ------------------------------------------------------------------
    @app.errorhandler(HTTPException)
    def error_http(e):
        mensajes = {
            400: "Petición incorrecta",
            404: "Recurso no encontrado",
            405: "Método no permitido",
            413: "El cuerpo de la petición es demasiado grande",
            415: "Tipo de contenido no soportado, use application/json",
            429: "Demasiadas peticiones, intente más tarde",
        }
        return jsonify({"error": mensajes.get(e.code, e.name)}), e.code

    @app.errorhandler(Exception)
    def error_inesperado(e):
        db.session.rollback()
        app.logger.exception("Error inesperado")
        return jsonify({"error": "Error interno del servidor"}), 500

    # ------------------------------------------------------------------
    # CLI: flask crear-usuario  (la contraseña se pide oculta, no queda en el historial)
    # ------------------------------------------------------------------
    @app.cli.command("crear-usuario")
    @click.option("--username", prompt=True)
    @click.option("--rol", type=click.Choice(["admin", "empleado"]), default="admin", show_default=True)
    @click.password_option()
    def crear_usuario(username, rol, password):
        from models import Usuario
        from validators import validar_usuario
        limpio, errores = validar_usuario({"username": username, "password": password, "rol": rol})
        if errores:
            raise click.ClickException(f"Datos inválidos: {errores}")
        if Usuario.query.filter_by(username=limpio["username"]).first():
            raise click.ClickException("Ese usuario ya existe")
        u = Usuario(username=limpio["username"], rol=limpio["rol"])
        u.set_password(limpio["password"])
        db.session.add(u)
        db.session.commit()
        click.echo(f"Usuario '{u.username}' creado con rol {u.rol}")

    return app


if __name__ == "__main__":
    # debug=False por defecto: el modo debug expone un depurador interactivo
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")
