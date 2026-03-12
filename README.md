# HETU SafePlay

Full-stack-sovellus suomalaisten henkilötunnusten (HETU) turvalliseen tallentamiseen. HETU validoidaan, salataan Fernetillä ja tallennetaan PostgreSQL-tietokantaan.

## Teknologiat

- **Backend:** FastAPI, Pydantic, SlowAPI (rate limiting), psycopg2, cryptography (Fernet)
- **Frontend:** HTML/JS (yksi sivu)
- **Tietokanta:** PostgreSQL
- **Deploy:** Render.com (render.yaml)

## Paikallinen käynnistys

1. Kloonaa repo ja luo virtuaaliympäristö:

```bash
git clone git@github.com:KangasCode/fastapi.git
cd fastapi
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Kopioi ympäristömuuttujat ja täytä arvot:

```bash
cp .env.example .env
```

- **SALAUSAVAIN:** Luo komennolla  
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- **DATABASE_URL:** PostgreSQL-yhteysmerkkijono (esim. `postgresql://user:pass@localhost:5432/hetu_safeplay`)

3. Käynnistä sovellus:

```bash
uvicorn main:app --reload --forwarded-allow-ips="*"
```

Sovellus: http://127.0.0.1:8000

## API

- **POST /api/hetu**  
  Body: `{"hetu": "010190-123A"}`  
  Vastaukset: 200 (ok), 422 (virheellinen HETU), 429 (rate limit), 500 (palvelinvirhe)

## Render.com-deploy

1. Yhdistä tämä repo Renderiin (Blueprint).
2. Aseta **SALAUSAVAIN** (Secret) Dashboardista (sync: false).
3. Tietokanta ja ENV luodaan render.yaml:n mukaan.

Käynnistyskomento:  
`uvicorn main:app --host 0.0.0.0 --port $PORT --forwarded-allow-ips="*"`

## Tiedostot

| Tiedosto        | Kuvaus                    |
|-----------------|---------------------------|
| `main.py`       | FastAPI-backend, API, DB  |
| `index.html`    | Frontend                  |
| `requirements.txt` | Python-riippuvuudet   |
| `render.yaml`   | Render.com Blueprint      |
| `.env.example`  | Esimerkki ympäristömuuttujista |

---

## Suunnitelma (Plan)

Suunnitelma full-stack-sovelluksesta: FastAPI-backend, PostgreSQL, Fernet-salaus, HTML/JS-frontend. Valmis Render.com-julkaisuun.

### Arkkitehtuuri

```mermaid
flowchart TB
    subgraph frontend [Frontend]
        HTML["index.html"]
        Input["HETU Input"]
        Fetch["POST /api/hetu"]
    end

    subgraph backend [Backend]
        FastAPI[FastAPI]
        CORS[CORSMiddleware]
        Limiter["SlowAPI 5/min per IP"]
        Validator["Pydantic + HETU"]
        Fernet[Fernet Encrypt]
        DB[(PostgreSQL)]
    end

    HTML --> Input
    Input --> Fetch
    Fetch --> FastAPI
    FastAPI --> CORS
    FastAPI --> Limiter
    Limiter --> Validator
    Validator --> Fernet
    Fernet --> DB
```

### Tiedostorakenne

```
SafePlay/
├── main.py           # FastAPI-backend, API, validointi, salaus, DB
├── requirements.txt  # Riippuvuudet
├── index.html        # Frontend (yksi sivu)
├── render.yaml       # Render.com Blueprint
└── .env.example      # Esimerkki ympäristömuuttujista
```

### 1. Frontend (index.html)

- Otsikko: "dont worry its safe..."
- Yksi `<input>` HETU-syöttökenttälle (keskellä ruutua)
- Lähetys: `POST /api/hetu` body `{"hetu": "010190-123A"}`
- Vastaukset: 200 (onnistui), 422 (virheellinen muoto/tarkistusmerkki), 429 (rate limit), 500 (palvelinvirhe)
- CORS: backend rajoittaa tuotannossa originin (leevinhetuntarkistuskone.fi)

### 2. Backend (main.py)

- FastAPI, CORS, staattinen index.html juurella
- **Rate limiting (SlowAPI):** 5 pyyntöä/minuutissa per IP, `get_remote_address`; proxy-tuki `--forwarded-allow-ips="*"`
- **Endpoint:** `POST /api/hetu` → validointi, salaus, INSERT

### 3. Pydantic & HETU-logiikka

- **Regex:** `^\d{6}[A+\-]\d{3}[A-Z0-9]$`
- **Pituus:** max 15 merkkiä
- **Tarkistusmerkki:** 9-numeroinen luku `DDMMYY` + `ZZZ` → `% 31` → taulukko `"0123456789ABCDEFHJKLMNPRSTUVWXY"`; väärä → 422

### 4. Salaus (Fernet)

- Avain: `SALAUSAVAIN` ympäristömuuttujasta
- Salaa ennen tallennusta: `fernet.encrypt(hetu.encode())`

### 5. Tietokanta (PostgreSQL)

- psycopg2, `DATABASE_URL`
- Taulu: `hetut (id SERIAL PRIMARY KEY, encrypted_hetu BYTEA)`
- Prepared statement: `INSERT INTO hetut (encrypted_hetu) VALUES (%s)`
- Taulu luodaan käynnistyksessä: `CREATE TABLE IF NOT EXISTS hetut ...`

### 6. Render.com

- Ympäristö: `SALAUSAVAIN`, `DATABASE_URL` (Blueprint), `ENV=production`
- Käynnistys: `uvicorn main:app --host 0.0.0.0 --port $PORT --forwarded-allow-ips="*"`

### HETU-tarkistusmerkin algoritmi

- Muoto: `DDMMYY` + välimerkki + `ZZZ` + tarkistusmerkki
- Tarkistukseen: `DDMMYY` + `ZZZ` (9 numeroa) → `remainder = (DDMMYYZZZ) % 31` → `"0123456789ABCDEFHJKLMNPRSTUVWXY"[remainder]`
- Esimerkki: `120464-126J` → `120464126 % 31 = 17` → `J` ✓

---

## Lisenssi

Projekti-omistajan määrittämä.
