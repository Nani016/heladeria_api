# API - Sistema de Gestión de Pedidos para una Heladería

API REST con **Flask + SQLAlchemy (ORM) + SQLite**, con autenticación JWT,
roles, validación estricta de datos y pruebas unitarias (102 pruebas).

## Estructura

```
heladeria_api/
├── app.py            # Fábrica de la app, cabeceras de seguridad, errores, comando CLI
├── config.py         # Configuración desde variables de entorno
├── extensions.py     # db, migrate, jwt, limiter
├── models.py         # Usuario, TokenRevocado, Pedido
├── auth.py           # /auth/login, /logout, /perfil, /registro + roles
├── routes.py         # Los 8 endpoints de /pedidos
├── validators.py     # Validación y sanitización de entradas
├── tests/            # Pruebas unitarias (pytest)
├── migrations/       # Migraciones versionadas (Alembic)
├── .env.example      # Plantilla de variables de entorno
└── heladeria_api.postman_collection.json
```

## Instalación en Windows (CMD)

```bat
cd heladeria_api
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
```

Abre `.env` con el Bloc de notas y pega una clave secreta en `JWT_SECRET_KEY`.
Para generarla:

```bat
python -c "import secrets; print(secrets.token_hex(32))"
```

> En PowerShell usa `Copy-Item .env.example .env` y `$env:FLASK_APP="app.py"`.

## Base de datos (migraciones)

La carpeta `migrations/` ya viene incluida, así que **no** ejecutes `flask db init`.

```bat
set FLASK_APP=app.py
flask db upgrade
```

Esto crea `instance\heladeria.db` con las tablas listas.

## Crear el primer administrador

No existe registro público: el primer admin se crea por consola. La contraseña
se pide oculta (no queda en el historial).

```bat
flask crear-usuario --username admin --rol admin
```

Contraseña: mínimo 10 caracteres, con mayúscula, minúscula y número.

## Ejecutar

```bat
python app.py
```

La API queda en `http://127.0.0.1:5000`.

## Pruebas unitarias

```bat
python -m pytest -q
```

Cubren autenticación, los 8 endpoints, validaciones, roles, inyección SQL,
XSS, tokens manipulados, límite de tamaño y límite de intentos de login.

## Endpoints

Todos (excepto login) requieren la cabecera `Authorization: Bearer <token>`.

| Método | Ruta                         | Rol         | Descripción                                  |
|--------|------------------------------|-------------|----------------------------------------------|
| POST   | /auth/login                  | público     | Devuelve el token JWT                        |
| POST   | /auth/logout                 | autenticado | Revoca el token actual                       |
| GET    | /auth/perfil                 | autenticado | Datos del usuario actual                     |
| POST   | /auth/registro               | admin       | Crea usuarios                                |
| POST   | /pedidos                     | autenticado | Registrar un pedido                          |
| GET    | /pedidos                     | autenticado | Listar (`?pagina=&por_pagina=&estado=`)      |
| GET    | /pedidos/:id                 | autenticado | Consultar un pedido                          |
| PUT    | /pedidos/:id                 | autenticado | Actualizar completo                          |
| PATCH  | /pedidos/:id/estado          | autenticado | Cambiar solo el estado                       |
| DELETE | /pedidos/:id                 | **admin**   | Eliminar                                     |
| GET    | /pedidos/fecha/:YYYY-MM-DD   | autenticado | Pedidos de una fecha (+ minutos totales)     |
| GET    | /pedidos/proximos?horas=48   | autenticado | Pedidos activos que se entregan pronto       |

Estados: `Pendiente`, `En preparación`, `Listo`, `Entregado`, `Cancelado`.
Un pedido `Entregado` o `Cancelado` ya no se puede modificar.

Ejemplo de pedido:

```json
{
  "cliente": "Kevin Florez",
  "tipo_producto": "Torta helada",
  "sabor": "Chocolate",
  "cantidad": 20,
  "toppings": "Chispas de colores",
  "fecha_entrega": "2027-03-20",
  "hora_entrega": "16:00",
  "tiempo_preparacion": 180
}
```

## Seguridad implementada

| Aspecto | Cómo |
|---|---|
| Autenticación | JWT con expiración (30 min por defecto) |
| Cierre de sesión real | Logout guarda el token en una lista de revocados |
| Autorización | Roles `admin` / `empleado`; borrar y crear usuarios solo admin |
| Contraseñas | Hash con sal (scrypt), política de complejidad, nunca en texto plano |
| Enumeración de usuarios | Mismo mensaje y mismo tiempo de respuesta con usuario inexistente |
| Fuerza bruta | Límite de 5 logins por minuto por IP (HTTP 429) |
| Inyección SQL | Solo ORM, sin SQL crudo; entradas validadas |
| XSS | Se rechazan `<`, `>` y caracteres de control |
| Validación | Tipos, rangos y longitudes estrictos; fechas pasadas rechazadas |
| Mass assignment | Solo se leen campos permitidos; `id`/`creado_por` no se pueden inyectar |
| Tamaño de petición | Máximo 16 KB (HTTP 413) |
| Cabeceras HTTP | nosniff, X-Frame-Options, CSP, HSTS, no-store |
| CORS | Cerrado por defecto; se abre solo con `CORS_ORIGINS` |
| Errores | Siempre JSON genérico, sin trazas ni detalles internos |
| Secretos | Todo en `.env`; la app no arranca sin `JWT_SECRET_KEY` |
| Migraciones | Cambios de tablas siempre con `flask db migrate` + `upgrade` |

**Para producción:** servir detrás de HTTPS, usar un servidor WSGI (gunicorn/waitress)
en vez del servidor de desarrollo y un `RATELIMIT_STORAGE_URI` compartido (Redis).

## Postman

1. Importa `heladeria_api.postman_collection.json` (**Import** en la pestaña *Collections*).
2. En la colección, pestaña **Variables**, cambia `admin_pass` por la contraseña de tu admin.
3. Ejecuta **0. Login**: el token se guarda solo en `{{token}}`.
4. Ejecuta **1. Crear pedido** y luego **2. Pedidos por fecha**.
