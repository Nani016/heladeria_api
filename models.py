from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

ESTADOS_VALIDOS = ["Pendiente", "En preparación", "Listo", "Entregado", "Cancelado"]
ESTADOS_FINALES = ["Entregado", "Cancelado"]
ROLES_VALIDOS = ["admin", "empleado"]


def _ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(db.Model):
    """Usuario del sistema. La contraseña NUNCA se guarda en texto plano."""

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="empleado")
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=_ahora)

    def set_password(self, password):
        # scrypt (por defecto en werkzeug) con sal aleatoria
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "rol": self.rol, "activo": self.activo}


class TokenRevocado(db.Model):
    """Lista de tokens JWT invalidados con el logout."""

    __tablename__ = "tokens_revocados"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    revocado_en = db.Column(db.DateTime, default=_ahora)


class Pedido(db.Model):
    """Pedido de la heladería."""

    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    tipo_producto = db.Column(db.String(60), nullable=False)  # Copa, Cono, Litro, Torta helada...
    sabor = db.Column(db.String(60), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)  # porciones / unidades
    toppings = db.Column(db.String(120), nullable=True)
    fecha_entrega = db.Column(db.Date, nullable=False, index=True)
    hora_entrega = db.Column(db.Time, nullable=False)
    tiempo_preparacion = db.Column(db.Integer, nullable=False)  # minutos
    estado = db.Column(db.String(30), nullable=False, default="Pendiente")
    creado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    creado_en = db.Column(db.DateTime, default=_ahora)

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente,
            "tipo_producto": self.tipo_producto,
            "sabor": self.sabor,
            "cantidad": self.cantidad,
            "toppings": self.toppings,
            "fecha_entrega": self.fecha_entrega.isoformat(),
            "hora_entrega": self.hora_entrega.strftime("%H:%M"),
            "tiempo_preparacion": self.tiempo_preparacion,
            "estado": self.estado,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
        }
