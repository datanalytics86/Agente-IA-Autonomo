# Contrato de integraciones

Cada proveedor tiene un `Protocol` en el módulo del adaptador, una clase real y una clase `Fake`. La fábrica `build_<nombre>(settings) -> Protocol` elige `Fake` si falta la credencial, si `DRY_RUN=true`, o si `APP_MODE=demo`. La clase real existe igual y se prueba con `respx` sin red.

El triple candado (§3.2, `dominio.md`) se evalúa dentro del adaptador de envío, no solo en el job.

Ningún adaptador envía Instagram, LinkedIn ni WhatsApp en frío. Esos canales crean `messages.status=manual_pending`.

## LLM — `engine/integrations/llm/base.py`

```python
class LlmClient(Protocol):
    def complete_json(self, prompt_name: str, schema: type[BaseModel], data: dict, model: str | None = None) -> BaseModel: ...
```

- Carga `engine/prompts/<prompt_name>.md`, exige `version:` en el front matter y la guarda en `llm_calls.prompt_version`.
- Valida con pydantic. Reintenta 2 veces adjuntando el error.
- Si no hay key, el gasto del día ≥ `LLM_DAILY_BUDGET_USD`, o el tercer intento falla: devuelve el fallback registrado por el agente y escribe `events.level=warn`.
- `FakeLlm` es determinista a partir de `data` (sin aleatoriedad salvo la semilla de simulación).

Precios para `cost_usd` (octubre 2026, docs.x.ai): `grok-4.7` y `grok-4.6` a 2 USD / 1M entrada y 6 USD / 1M salida. Si el modelo no está en la tabla, costo 0 y evento `warn`.

## Places — `engine/integrations/places/base.py`

```python
class PlaceHit(BaseModel):
    place_id: str
    name: str
    formatted_address: str
    website_uri: str | None
    rating: float | None
    user_rating_count: int | None
    business_status: str
    types: list[str]
    google_maps_uri: str | None
    national_phone_number: str | None

class LeadSource(Protocol):
    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]: ...
```

`GooglePlacesSource` llama `places:searchText` con `X-Goog-FieldMask` limitado a los campos de `PlaceHit`. `DemoSource` genera negocios verosímiles y estables con semilla.

Filtros: `OPERATIONAL`, rating ≥ `SCOUT_MIN_RATING`, reseñas ≥ `SCOUT_MIN_REVIEWS`. Cadenas y franquicias se excluyen por lista local (`engine/integrations/places/chains.py`).

## PageSpeed y auditoría — `engine/integrations/pagespeed/base.py`

```python
class WebAuditor(Protocol):
    def audit(self, url: str | None) -> WebsiteAudit: ...
```

Sin URL, `opportunity_score` alto (80–95) y `contact_email=None`. Con URL: HTTPS, viewport, año de copyright, `Last-Modified`, peso, CMS, enlaces rotos de la home, PageSpeed móvil. El contacto sale solo de esa página (`mailto:`, schema.org, página de contacto enlazada). Se guarda `source_url`. No se adivinan buzones. Se respeta `robots.txt`. User-Agent identificable con `PUBLIC_BASE_URL`. Máximo 1 req/s por dominio.

## Video — `engine/integrations/video/base.py`

```python
class VideoRenderer(Protocol):
    def render(self, landing_path: Path, storyboard: Storyboard) -> VideoResult: ...
```

`PlaywrightFfmpegRenderer` captura 1080×1920 y arma un MP4 9:16 de ~12 s. Si no hay Chromium o FFmpeg, `StoryboardRenderer` escribe Markdown y un evento `info`. Nunca lanza por ausencia de binarios.

## Email — `engine/integrations/email/`

Dos protocolos distintos.

```python
class TransactionalEmail(Protocol):
    def send(self, to: str, subject: str, text: str, html: str, headers: dict[str, str]) -> SendResult: ...

class OutreachEmail(Protocol):
    def send(self, message_id: str, to: str, subject: str, text: str, html: str) -> SendResult: ...

class InboundPoller(Protocol):
    def poll(self) -> list[InboundMail]: ...
```

`OutreachEmail.send` aplica el triple candado y la supresión. Arma `List-Unsubscribe` y `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Sin píxel. `Reply-To` es el buzón IMAP. El transaccional rechaza si el mensaje no tiene `consent` o no es un correo de sistema (recibo, portal, derechos).

`FakeOutreach` guarda los envíos en memoria/BD de simulación, aplica 3 % de rebotes cuando la simulación lo pide, y no abre sockets.

## Agenda — `engine/integrations/booking/base.py`

```python
class BookingProvider(Protocol):
    def link_for(self, lead_id: str) -> str: ...
    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> BookingEvent: ...
```

`BookingEvent` trae `lead_id` (metadata o UTM), `start`, `provider_event_id`. Firma inválida → error que la API traduce a 401.

## Pagos — `engine/integrations/payments/base.py`

```python
class PaymentProvider(Protocol):
    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference: ...
    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str: ...  # payment id
    def fetch_payment(self, provider_payment_id: str) -> PaymentFact: ...
```

Mercado Pago es el default. El webhook no confía en el body: pide `fetch_payment`. `provider_payment_id` duplicado no crea otra orden ni otro pago.

## Meta — `engine/integrations/meta/base.py`

```python
class MetaInbound(Protocol):
    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None: ...
    def parse_webhook(self, body: bytes, signature: str) -> list[InboundMessage]: ...
    def send_reply(self, recipient: str, text: str, *, user_initiated: bool) -> SendResult: ...
```

`send_reply` exige `user_initiated=True` y ventana de 24 h u opt-in ya registrado. Si no, deja `manual_pending` y no llama a la red.

## Hosting — `engine/integrations/hosting/base.py`

```python
class SiteHosting(Protocol):
    def publish(self, project_id: str, files: Path, domain: str | None) -> str: ...
    def domain_allowed(self, domain: str) -> bool: ...
```

`CaddyHosting.publish` copia el estático a `CLIENT_SITES_DIR/<slug>`. `domain_allowed` es la respuesta del endpoint `ask`: true solo si hay un `project.domain` igual y status `aprobado` o `publicado`.

## Storage

Los artefactos viven en disco (`engine/output/`). `storage.LocalStorage.put/get` es el protocolo. No hay S3 en esta versión.

## Fakes de simulación

`engine/simulation/providers.py` reutiliza las mismas clases Fake con un RNG `random.Random(seed)` y el reloj inyectado. Distribución inbound por defecto, sobre envíos entregados: 6 % interesado, 3 % pregunta de precio, 2 % opt-out, 1 % agendar, 1 % fuera de oficina, 1 % prompt-injection, resto silencio. Rebotes 3 %.
