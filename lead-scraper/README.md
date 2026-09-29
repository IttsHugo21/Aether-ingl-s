# Lead scraper — Meta Ads (Aether)

Busca en la **Biblioteca de Anuncios de Meta** (Facebook/Instagram) negocios
que ya están pagando anuncios en los sectores del ICP de Aether (joyería,
cosmética, moda, calzado, accesorios, hogar, deporte, mascotas, alimentación
premium, electrónica...), y saca un Excel priorizado con:

- quién es el anunciante, cuántos anuncios tiene activos y desde cuándo
- su web, y si tiene email / teléfono / WhatsApp / Instagram / TikTok
- una puntuación (0–100) y tier (A/B/C) según cuánto parece estar invirtiendo
- por qué ha sacado esa puntuación (motivos en texto)

Excluye automáticamente grandes marcas y marketplaces (`config/blocklist.txt`)
que no son un lead real para un servicio boutique.

## Instalación

```bash
cd lead-scraper
pip install -r requirements.txt
```

## Modo 1 (recomendado): API oficial de Meta

Desde la regulación DSA de la UE, la Ad Library API devuelve **todos** los
anuncios activos en países de la UE (no solo políticos), incluido el alcance
estimado. Es el modo más fiable y el único pensado para correr desde un
servidor/nube.

### Conseguir el token

1. Entra en [developers.facebook.com](https://developers.facebook.com) con tu
   cuenta de Facebook y crea una app (tipo "Business").
2. Verifica tu identidad para la Ad Library API en
   [facebook.com/id](https://www.facebook.com/id) (te piden DNI, es de Meta,
   no de nosotros).
3. Acepta las condiciones en
   [facebook.com/ads/library/api](https://www.facebook.com/ads/library/api).
4. Genera un **token de usuario** (o de app) desde el Graph API Explorer o tu
   app, con permiso de lectura pública (no necesita permisos especiales, la
   Ad Library es de acceso público una vez verificada tu identidad).
5. Cópialo a un archivo `.env` (copia `.env.example`) o expórtalo:

```bash
cp .env.example .env   # y pega tu token dentro
export META_ACCESS_TOKEN=EAAB...   # o carga el .env con tu gestor habitual
```

### Ejecutar

```bash
python main.py --mode api --all-sectors --country ES
python main.py --mode api --sectors joyeria cosmetica moda --max-ads 300
python main.py --mode api --sectors mascotas --keywords "comida ecológica perros"
```

El token tiene un límite de peticiones de Meta; el cliente reintenta solo con
espera automática si lo alcanzas, así que si tarda no está roto, respeta el
límite de Meta.

## Modo 2 (sin token): navegador en tu ordenador

Si no quieres pasar por la verificación de Meta, hay una alternativa que abre
la Biblioteca de Anuncios en un Chromium controlado y lee las respuestas que
la propia web recibe. **Debes correrlo desde tu propio ordenador**, no desde
un servidor o esta sesión en la nube: Meta bloquea el acceso a la Ad Library
web desde muchas IPs de datacenter/hosting.

```bash
pip install playwright
python -m playwright install chromium
python main.py --mode browser --sectors joyeria --no-headless
```

`--no-headless` te deja ver el navegador (útil si Meta pide resolver un
captcha la primera vez). Este modo es más frágil que la API (depende de cómo
Meta estructure su HTML/GraphQL en cada momento) — si deja de funcionar,
revisa `leads/browser.py`.

## Configurar sectores y exclusiones

- `config/sectors.yaml`: añade/quita sectores o palabras clave. La clave
  (`joyeria`, `cosmetica`...) es la que usas en `--sectors`.
- `config/blocklist.txt`: términos (nombre de página o dominio) que excluyen
  un lead — grandes marcas, marketplaces, etc. Una entrada por línea.

## Salida

Cada ejecución genera en `output/`:

- `leads_<fecha>.xlsx` — hoja "Leads" ordenada por puntuación (tabla con
  filtros), hoja "Excluidos" con los que cayeron en la blocklist y por qué.
- `leads_<fecha>.csv` — mismo contenido en CSV, sin excluidos.

## Cómo puntúa

`leads/score.py` prioriza señales de presupuesto real, no solo "aparece en un
anuncio":

| Señal | Por qué importa |
|---|---|
| Nº de anuncios activos | más anuncios simultáneos = más presupuesto |
| Días de campaña activa | campañas largas = gasto sostenido, no una prueba |
| Creatividades distintas | testear variantes cuesta dinero y indica cultura de performance |
| Alcance estimado en la UE | tamaño de la inversión |
| Web propia / e-commerce (Shopify, WooCommerce...) | tiene infraestructura para vender, no es solo una página de FB |
| Pixel de Meta instalado | mide conversiones → entiende de rendimiento de ads |
| Contacto encontrado (email/tel/WhatsApp) | puedes contactar de inmediato |

Tier A ≥ 65 puntos, B ≥ 40, C el resto. Ajusta los pesos en `score_lead()` si
quieres cambiar los criterios.

## Enriquecimiento web (opcional)

Por defecto, tras agregar los leads el script visita la web detectada de cada
uno (en paralelo, con timeout corto) para sacar email, teléfono, WhatsApp,
Instagram/TikTok y detectar el stack (Shopify/WooCommerce/PrestaShop/Wix) y si
tiene píxel de Meta/TikTok. Es best-effort: si una web falla o no responde, el
lead se queda sin esos datos pero no rompe el proceso. Desactívalo con
`--no-enrich` si solo quieres velocidad.

## Integración con el CRM ("CRM {Meta Ads}")

Cada ejecución también genera `output/crm_<fecha>.json`, con los leads ya en
el **esquema exacto** que espera el CRM (`marca`, `sector`, `pais`, `web`,
`anuncio_url`, `num_anuncios`, `tanda`, `estado`, `notas`, `fecha_tanda`), listo
para su colección `leads`.

Controla qué entra en ese archivo con:

```bash
python main.py --all-sectors --crm-min-tier B --crm-tanda 3
```

- `--crm-min-tier {A,B,C}`: solo incluye leads de ese tier o mejor (por
  defecto `C` = todos los no excluidos).
- `--crm-tanda N`: número de tanda a asignar a este lote.
- `--crm-json ruta.json`: cambia dónde se escribe el archivo.

**Importante:** este script *genera* el JSON, pero no lo escribe él mismo en
el CRM. La base de datos de ese artifact vive en la organización de claude.ai
de quien lo creó, y una sesión de Claude Code invitada como colaboradora no
tiene permiso para leer/escribir su base de datos (lo intentamos: el intento
de acceso devuelve "no access" explícitamente). Para meter los leads dentro:

1. Abre el CRM en **claude.ai** (no en Claude Code) desde la cuenta dueña del
   artifact, y pide ahí que importe el contenido de `crm_<fecha>.json` a la
   colección `leads` — esa sesión sí puede escribir en su propia base de
   datos.
2. O, para unos pocos leads, cópialos a mano con el botón **"+ Añadir lead"**
   del propio CRM — los campos del formulario coinciden uno a uno con las
   claves del JSON.

## Tests

```bash
pip install pytest
python -m pytest
```

Los tests cubren la config de sectores, la agregación de anuncios en leads,
el scoring y la exportación — no hacen llamadas de red reales.

## Límites conocidos

- La API de Meta solo cubre anuncios **activos o recientes**; no tiene
  histórico completo indefinido.
- El modo `browser` depende de la estructura interna de Facebook, que cambia
  sin aviso.
- La detección de "web propia" es heurística (se basa en los links/captions
  de los propios anuncios): revisa siempre antes de usar el dato para
  contactar.
- El enriquecimiento web no salta paywalls, captchas ni cookies: si la web
  bloquea bots, ese lead quedará sin email/teléfono automático (queda su
  perfil de Meta e Instagram igualmente).
