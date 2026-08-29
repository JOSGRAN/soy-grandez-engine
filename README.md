# Soy Grandez Engine - Motor de Automatización

Motor de automatización en Python para plataforma de streaming, diseñado para integrarse con un backend Laravel 12 (Filament) mediante API REST y base de datos MySQL compartida.

## 📋 Fase 1 - Entregables Completados

### Estructura del Proyecto

```
soy-grandez-engine/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuración con Pydantic Settings
├── database/
│   ├── __init__.py
│   ├── connection.py        # Conexión SQLAlchemy a MySQL
│   ├── models.py            # Modelos de datos (Credential, Account, Subscription)
│   └── repository.py       # Repositorio para operaciones de base de datos
├── services/
│   ├── __init__.py
│   ├── auth_service.py      # Autenticación Laravel Sanctum
│   ├── laravel_api_client.py # Cliente HTTP para API de Laravel
│   ├── capsolver_service.py # Servicio para resolver CAPTCHAs
│   ├── browser_manager.py   # Gestor de navegador Playwright
│   ├── email_otp_service.py # Servicio de lectura de OTP Gmail
│   └── orchestrator_service.py # Orquestador general de automatización
├── core/
│   ├── __init__.py
│   ├── exceptions.py        # Excepciones personalizadas
│   ├── logger.py            # Sistema de logging avanzado
│   └── task_manager.py      # Gestor de tareas con reintentos
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py      # Clase base para scrapers
│   ├── gosplit_scraper.py   # Scraper para GoSplit
│   ├── sharesub_scraper.py  # Scraper para ShareSub
│   └── streaming_scraper.py # Scraper para Netflix/Disney+
├── main.py                  # Punto de entrada CLI consolidado
├── worker.py                # Worker para ejecución en segundo plano
├── test_phase2.py          # Pruebas de integración Fase 2
├── test_phase3.py          # Pruebas de integración Fase 3
├── requirements.txt         # Dependencias de Python
├── .env.example            # Plantilla de variables de entorno
└── README.md               # Esta documentación
```

## 🚀 Instalación y Configuración

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno

Copiar el archivo `.env.example` a `.env` y configurar las variables:

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

```env
# Database Configuration (MySQL - Laravel Shared Database)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=laravel_database
DB_USER=laravel_user
DB_PASSWORD=laravel_password

# Laravel API Configuration
LARAVEL_API_URL=http://localhost:8000/api
LARAVEL_API_TOKEN=your_laravel_sanctum_token_here
LARAVEL_API_EMAIL=admin@example.com
LARAVEL_API_PASSWORD=admin_password

# Encryption Key (for credentials decryption)
ENCRYPTION_KEY=your_32_byte_encryption_key_here

# Capsolver Configuration (for CAPTCHA solving)
CAPSOLVER_API_KEY=your_capsolver_api_key_here

# Browser Automation Settings
BROWSER_HEADLESS=false
BROWSER_TIMEOUT=30000
SCREENSHOT_ON_ERROR=true

# Gmail API Configuration (for OTP reading)
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.pickle
GMAIL_OTP_TIMEOUT=300
GMAIL_OTP_RETRY_INTERVAL=10

# Orchestrator Configuration
ORCHESTRATOR_MAX_CONCURRENT_TASKS=3
ORCHESTRATOR_SYNC_INTERVAL_MINUTES=60
ORCHESTRATOR_TASK_TIMEOUT=300
ORCHESTRATOR_MAX_RETRIES=3
ORCHESTRATOR_RETRY_DELAY=5

# Application Settings
APP_ENV=development
LOG_LEVEL=INFO
```

## 🔧 Componentes Principales

### Base de Datos (MySQL)

- **Conexión**: SQLAlchemy con PyMySQL
- **Modelos**:
  - `Credential`: Credenciales cifradas de plataformas (GoSplit, ShareSub, Streaming)
  - `Account`: Cuentas de usuarios con estados y fechas de suscripción
  - `Subscription`: Detalles de suscripciones y planes
- **Repositorio**: Métodos para consultar cuentas vencidas y actualizar estados

### Cliente API (Laravel Sanctum)

- **Autenticación**: Token Bearer o login con email/password
- **Endpoints implementados**:
  - `GET /api/accounts` - Listado de cuentas
  - `GET /api/subscriptions/expired` - Suscripciones vencidas
  - `PUT /api/accounts/{id}/password` - Actualizar contraseña
  - `PUT /api/accounts/{id}/status` - Actualizar estado
  - `POST /api/accounts/sync` - Sincronizar datos de cuenta

### Automatización Web (Fase 2)

#### Servicio Capsolver
- **Integración**: API de Capsolver para resolver CAPTCHAs automáticamente
- **Tipos soportados**:
  - Cloudflare Turnstile
  - reCAPTCHA v2/v3
  - hCaptcha
- **Uso**: Detección automática y resolución de desafíos durante navegación

#### Gestor de Navegador (Playwright)
- **Anti-detección**: Headers realistas, desactivación de flags de automatización
- **Funcionalidades**:
  - Navegación asíncrona con manejo de cookies
  - Screenshots automáticos para debugging
  - Inyección de scripts anti-detección
  - Soporte para proxies
- **Modos**: Headless (producción) y headed (desarrollo)

#### Scrapers por Plataforma
- **GoSplit Scraper**: Login, gestión de cuentas, cambio de credenciales
- **ShareSub Scraper**: Login, gestión de suscripciones, cambio de credenciales
- **Streaming Scraper**: Soporte para Netflix y Disney+, gestión de perfiles

### Automatización de OTP (Fase 3)

#### Servicio de Lectura de OTP Gmail
- **Integración**: Gmail API con OAuth2 para lectura de correos
- **Funcionalidades**:
  - Búsqueda de correos de verificación por remitente
  - Extracción de códigos OTP mediante patrones regex
  - Soporte para códigos de 4-6 dígitos y alfanuméricos
  - Extracción de enlaces de verificación
  - Marcado automático de correos como leídos
- **Plataformas soportadas**: Netflix, Disney+, GoSplit, ShareSub
- **Integración con scrapers**: Detección automática de prompts OTP e inserción de códigos

### Orquestador General (Fase 4)

#### Servicio de Orquestación
- **Integración**: Coordinación de todos los componentes en flujos automatizados
- **Funcionalidades**:
  - Sincronización periódica de cuentas vencidas desde Laravel API
  - Ejecución secuencial de tareas: credenciales → scraper → CAPTCHA → OTP → actualización
  - Gestión de tareas concurrentes con límites configurables
  - Sistema de reintentos con backoff exponencial
  - Manejo de dependencias entre tareas
  - Actualización automática de Laravel con resultados
- **Sistema de Tareas**:
  - TaskManager con soporte para dependencias
  - Estados de tarea: PENDING, RUNNING, COMPLETED, FAILED, RETRYING
  - Timeout configurable por tarea
  - Máximo número de reintentos configurable
- **Logging Avanzado**:
  - Rotación de archivos de log (10MB, 5 backups)
  - Logs separados por nivel (general y errores)
  - Context manager para medición de tiempo de tareas
  - Logs estructurados con timestamps y ubicación

#### Excepciones Personalizadas
- `OrchestratorException`: Base para errores de orquestación
- `ScraperException`: Errores de scrapers
- `OTPException`: Errores de manejo de OTP
- `APIException`: Errores de comunicación con APIs
- `DatabaseException`: Errores de base de datos
- `RetryableException`: Errores que pueden reintentarse
- `NonRetryableException`: Errores que no deben reintentarse

## 🧪 Ejecutar Pruebas de Integración

### Fase 1 - Pruebas de Base de Datos y API

```bash
python main.py --test
```

Las pruebas validan:
1. ✅ Conexión a base de datos MySQL
2. ✅ Consulta de credenciales y cuentas vencidas
3. ✅ Autenticación con Laravel Sanctum
4. ✅ Obtención de cuentas desde API de Laravel
5. ✅ Consulta de suscripciones vencidas desde API

### Fase 2 - Pruebas de Automatización Web

```bash
# Instalar navegadores de Playwright (primera vez)
playwright install chromium

# Ejecutar pruebas de Fase 2
python main.py --phase2
```

Las pruebas validan:
1. ✅ Inicialización del navegador Playwright
2. ✅ Servicio Capsolver para resolución de CAPTCHAs
3. ✅ Scraper de GoSplit (mock test)
4. ✅ Scraper de ShareSub (mock test)
5. ✅ Scraper de Streaming (Netflix/Disney+ mock test)
6. ✅ Simulación de manejo de Cloudflare Turnstile

### Fase 3 - Pruebas de OTP Gmail

```bash
# Configurar Gmail API (primera vez)
# 1. Ir a Google Cloud Console
# 2. Crear proyecto y habilitar Gmail API
# 3. Crear credenciales OAuth 2.0 (Desktop app)
# 4. Descargar credentials.json
# 5. Colocarlo en el directorio del proyecto

# Ejecutar pruebas de Fase 3
python main.py --phase3
```

Las pruebas validan:
1. ✅ Autenticación con Gmail API (OAuth2)
2. ✅ Extracción de códigos OTP mediante regex
3. ✅ Búsqueda de correos de verificación
4. ✅ Integración OTP con Streaming Scraper
5. ✅ Extracción de enlaces de verificación
6. ✅ Conteo de correos no leídos

### Fase 4 - Orquestador y Sincronización

```bash
# Ejecutar sincronización una vez
python main.py --sync

# Procesar una cuenta individual
python main.py --account 123 netflix

# Ejecutar como worker en segundo plano
python main.py --worker

# O usar el script worker dedicado
python worker.py
```

Las pruebas validan:
1. ✅ Inicialización del orquestador
2. ✅ Obtención de cuentas vencidas desde Laravel API
3. ✅ Procesamiento secuencial de cuentas
4. ✅ Integración con scrapers, CAPTCHA y OTP
5. ✅ Actualización de credenciales en base de datos
6. ✅ Notificación a Laravel API con resultados
7. ✅ Ejecución programada con intervalos configurables

## 📦 Dependencias

### Fase 1 - Base de Datos y API
- `httpx==0.27.0` - Cliente HTTP async moderno
- `sqlalchemy==2.0.30` - ORM para base de datos
- `pymysql==1.1.0` - Driver MySQL
- `python-dotenv==1.0.1` - Gestión de variables de entorno
- `pydantic==2.7.1` - Validación de datos
- `pydantic-settings==2.2.1` - Configuración tipada
- `cryptography==42.0.5` - Cifrado de credenciales

### Fase 2 - Automatización Web
- `playwright==1.43.0` - Automatización de navegador
- `capsolver==0.1.0` - Servicio de resolución de CAPTCHAs

### Fase 3 - Gmail API y OTP
- `google-api-python-client==2.128.0` - Cliente de Google APIs
- `google-auth-httplib2==0.2.0` - Autenticación Google HTTP
- `google-auth-oauthlib==1.2.0` - OAuth 2.0 para Google

### Fase 4 - Orquestación y Tareas
- `apscheduler==3.10.4` - Programador de tareas periódicas

## 🔐 Seguridad

- Las credenciales se almacenan cifradas en la base de datos
- Autenticación mediante tokens Bearer de Laravel Sanctum
- Variables de entorno para datos sensibles
- Conexión a base de datos con pool de conexiones
- Anti-detección de automatización web con Playwright
- Resolución segura de CAPTCHAs mediante Capsolver
- Autenticación OAuth2 segura para Gmail API
- Tokens de acceso almacenados localmente con pickle

## 🐳 Despliegue con Docker

El motor cuenta con una capa de contenedorización optimizada para desarrollo local (WSL) y producción en VPS (Contabo).

### Archivos Generados

| Archivo | Propósito |
|---------|-----------|
| [Dockerfile](file:///c:/xampp/htdocs/soy-grandez-engine/Dockerfile) | Build multistage (Python 3.11-slim + dependencias Playwright/Chromium |
| [docker-compose.yml](file:///c:/xampp/htdocs/soy-grandez-engine/docker-compose.yml) | Orquestación de servicios con profiles para dev/prod/sync/test |
| [docker-entrypoint.sh](file:///c:/xampp/htdocs/soy-grandez-engine/docker-entrypoint.sh) | Script de inicialización + validación de variables + instalación on-demand de Chromium |
| [.dockerignore](file:///c:/xampp/htdocs/soy-grandez-engine/.dockerignore) | Optimización del contexto de build |

---

### 🚀 Despliegue Rápido

#### 1. Preparación

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales. **Importante para producción**:
- `BROWSER_HEADLESS=true`
- `APP_ENV=production`
- `LOG_LEVEL=INFO`
- `DB_HOST` debe apuntar al nombre del servicio MySQL o IP del VPS

#### 2. Red Compartida con Backend

El `docker-compose.yml` se conecta a una red Docker externa `laravel-backend-net` para comunicarse con Laravel y MySQL del stack principal.

**Antes del primer despliegue (solo una vez):**

```bash
docker network create laravel-backend-net
```

O define tu propia red en el `.env`:
```env
BACKEND_NETWORK_NAME=mi-red-personalizada
```

Si el motor necesita conectarse a recursos fuera de Docker (MySQL o API en el host), usa `host.docker.internal` o la IP real del VPS.

---

### 💻 Entorno de Desarrollo Local (WSL / Linux)

Modo interactivo con **hot-reload del código fuente**:

```bash
docker compose --profile dev up --build -d
```

Ver logs en tiempo real:
```bash
docker compose --profile dev logs -f engine-dev
```

Ejecutar comandos ad-hoc (sync, tests, etc.):
```bash
docker compose --profile dev exec engine-dev python main.py --test
docker compose --profile dev exec engine-dev python main.py --sync
docker compose --profile dev exec engine-dev python main.py --account 123 netflix
```

Detener:
```bash
docker compose --profile dev down
```

---

### 🌐 Entorno de Producción (VPS Contabo)

#### Levantar el worker en segundo plano:

```bash
docker compose --profile production up --build -d
```

Ver estado y logs:
```bash
docker compose --profile production ps
docker compose --profile production logs -f engine --tail 200
```

Verificar healthcheck:
```bash
docker inspect --format='{{.State.Health.Status}}' soy-grandez-engine
```

#### Ejecutar Sync una sola vez (production):

```bash
docker compose --profile sync-once up --build engine-sync
```

#### Ejecutar tests de integración (production):

```bash
docker compose --profile test up --build engine-test
```

#### Comandos útiles de mantenimiento:

```bash
# Reiniciar servicio
docker compose --profile production restart engine

# Rebuild sin cache
docker compose --profile production build --no-cache && docker compose --profile production up -d

# Eliminar contenedor, preservando volúmenes (logs, etc.)
docker compose --profile production down

# Limpieza completa (ELIMINA volúmenes de logs/cache - USAR CON CUIDADO)
docker compose down -v
```

---

### 📦 Volúmenes y Persistencia

| Volumen | Ruta en Host / Contenedor | Contenido |
|---------|---------------------------|-----------|
| `engine-logs` | `/app/logs` | Archivos de log rotados (app + errores) |
| `engine-screenshots` | `/app/screenshots` | Capturas de error de Playwright |
| `playwright-cache` | `/ms-playwright` | Binarios de Chromium cacheados |
| Bind mount (dev) | `./:/app` | Código fuente (solo perfil `dev`) |
| Bind mount creds | `./credentials.json` (ro) | OAuth2 Gmail API |
| Bind mount token | `./token.pickle` (ro) | Token OAuth persistido |

---

### ⚙️ Configuración de Recursos

Perfil production aplica límites:
- **CPU**: 2 cores
- **Memoria**: 2 GB límite / 512 MB reserva
- **SHM**: 1 GB compartida
- **Logs**: 5 archivos × 10 MB cada uno
- **Restart**: unless-stopped

Ajusta estos valores en `docker-compose.yml` según capacidad del VPS.

---

### 🔍 Troubleshooting Playwright dentro del contenedor

```bash
# Verificar que Chromium está instalado
docker compose --profile production exec engine playwright --version

# Instalar / reinstalar Chromium manualmente
docker compose --profile production exec engine python -m playwright install --with-deps chromium

# Correr prueba básica del navegador
docker compose --profile test up --build engine-test

# Si hay errores de shared memory
# Aumentar shm_size en docker-compose.yml o arrancar con --ipc=host
```

---

### 📝 Próximos Pasos (Fase 5)

- Implementar descifrado de credenciales con cryptography
- Sistema de colas distribuido (Celery/Redis) para escalabilidad
- Logging avanzado y monitoreo (Prometheus/Grafana)
- Integración continua con backend Laravel
- Sistema de reintentos con backoff exponencial mejorado
- Dashboard de monitoreo de automatizaciones
- Soporte para múltiples cuentas de Gmail simultáneas
- Webhooks para notificaciones en tiempo real
- Sistema de alertas y notificaciones
- Pruebas unitarias y de integración completas

## 👨‍💻 Desarrollo

Este proyecto está diseñado como un microservicio independiente que se comunica con el backend principal de Laravel mediante API REST y acceso directo a la base de datos MySQL compartida para operaciones de lectura/escritura de credenciales.

## 📄 Licencia

Propiedad de SoyTV Grandez - Motor de Automatización de Streaming
