import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """
    Configuración principal. Todas las credenciales salen de variables de
    entorno (.env), nunca del código fuente.
    """

    TESTING = False

    # --- Base de datos -------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "heladeria.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT -----------------------------------------------------------
    # Obligatoria: sin ella la app no arranca (evita desplegar con una
    # clave por defecto conocida por todos).
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.environ.get("JWT_EXPIRA_MINUTOS", "30"))
    )

    # --- Seguridad general ---------------------------------------------
    # Rechaza cuerpos de petición mayores a 16 KB (evita abusos de tamaño)
    MAX_CONTENT_LENGTH = 16 * 1024
    JSON_SORT_KEYS = False
    # Orígenes permitidos para CORS, separados por coma. Vacío = ninguno.
    CORS_ORIGINS = [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
    ]

    # --- Límite de peticiones (rate limiting) ---------------------------
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per hour")
    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute")

    @classmethod
    def validar(cls):
        if not cls.JWT_SECRET_KEY or len(cls.JWT_SECRET_KEY) < 32:
            raise RuntimeError(
                "Falta JWT_SECRET_KEY (mínimo 32 caracteres) en el archivo .env. "
                "Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


class TestingConfig(Config):
    """Configuración para pruebas: BD en memoria y sin rate limiting."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "clave-solo-para-pruebas-unitarias-0123456789abcdef"
    RATELIMIT_ENABLED = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
