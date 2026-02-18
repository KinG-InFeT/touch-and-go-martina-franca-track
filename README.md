# Touch and Go - Mod Track per Assetto Corsa

**v1.0.0**

Circuito kart **Touch and Go** di Martina Franca (TA), Puglia.
Tracciato tecnico su 900 metri, larghezza 8-9m, con layout **default (CW)** e **reverse (CCW)**.

Mod per Assetto Corsa (versione 2019 - v1.16.x). Supporta Linux (Steam/Proton) e Windows.

## Requisiti

| Requisito | Linux | Windows |
|-----------|-------|---------|
| Python | 3.10+ | 3.10+ |
| Blender | 5.0+ (snap o PATH) | 5.0+ (installer o PATH) |
| Assetto Corsa | Steam / Proton | Steam nativo |
| Content Manager | Sostituzione launcher | Copia exe |
| CSP | dwrite.dll + extension/ | dwrite.dll + extension/ |
| Font di sistema | Necessari (ac-fonts.zip) | Gia' presenti |

### Setup Python virtualenv

**Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Manager (GUI) — modo raccomandato

Il Manager (`manager.py`) e' il punto di ingresso principale del progetto: un'applicazione PyQt5
cross-platform (Linux e Windows) che gestisce l'intero ciclo di vita della mod, dalla build
all'installazione in Assetto Corsa.

**Linux:**
```bash
source .venv/bin/activate
python manager.py
```
**Windows:**
```cmd
.venv\Scripts\activate
python manager.py
```

Il Manager ha 4 tab:

- **Preview 3D** — Viewer OpenGL integrato che mostra il KN5 della pista senza aprire AC.
  Visualizza mesh, texture, empty AC (start, pit, timing) con indicatori colorati.
  All'avvio esegue automaticamente l'export KN5 per avere sempre la preview aggiornata al .blend.

- **Build** — Esegue la pipeline di build in 6 step con output in tempo reale:
  1. Export KN5 da Blender (converte la scena .blend in formato nativo AC)
  2. Setup struttura mod (genera surfaces.ini, cameras.ini, models.ini, ui_track.json, ecc.)
  3. Generazione AI line CW (estrae la centerline dal mesh 1ROAD per fast_lane.ai)
  4. Generazione blend reverse (apre il .blend CW, ruota gli empty di 180°)
  5. Export KN5 reverse (converte la scena reverse in KN5)
  6. Generazione AI line CCW (genera fast_lane.ai in senso antiorario)

  Il pulsante "Build All" li esegue tutti in sequenza; ogni step puo' anche essere lanciato singolarmente.
  Al termine copia entrambi i KN5 nella cartella mod e ricarica la preview 3D.

- **Install** — Installa la mod e i componenti aggiuntivi in Assetto Corsa, senza dipendenze bash.
  Rileva automaticamente il percorso di AC (Steam su Linux e Windows, multi-drive).
  Checkbox per selezionare cosa installare:
  - **Touch and Go** — copia la cartella mod in `content/tracks/`
  - **Pulizia cache** — rimuove cache AC (ai_grids, ai_payloads, meshes_metadata) e cache CM
  - **Content Manager** — cerca/scarica zip, estrae exe; su Linux lo imposta come launcher Steam
  - **Custom Shaders Patch** — cerca/scarica zip, estrae dwrite.dll e extension/
  - **Font di sistema** — installa verdana.ttf, segoeui.ttf (solo Linux, su Windows gia' presenti)

- **Parametri** — Editor per i parametri della pista (geometria, AI line, superfici, info).
  Salva e carica da `track_config.json`, usato da `setup_mod_folder.py` per generare i file di configurazione.

## Workflow — file master e reverse automatico

Il file Blender **`touch_and_go.blend`** e' il **sorgente principale unico** della pista.
Tutte le modifiche alla geometria, materiali, empty e texture si fanno **solo** in questo file.

Il layout **reverse** viene generato **automaticamente** durante la build:
- Lo script `create_reverse_blend.py` apre `touch_and_go.blend`, ruota tutti gli empty `AC_*`
  di 180° sull'asse Z (per invertire la direzione di partenza), e salva come `touch_and_go_reverse.blend`.
- La mesh 3D (asfalto, cordoli, muri, erba) resta **identica** — cambia solo la direzione di marcia.
- L'AI line reverse viene generata in senso antiorario (CCW).

**Non serve mai modificare `touch_and_go_reverse.blend` manualmente.**
Ogni modifica al file master `.blend` si propaga automaticamente alla versione reverse con la build successiva.

### Pipeline di build (6 step)

La pipeline e' gestita dal Manager, da `build_cli.py`, o da `build.sh`:

| Step | Descrizione | Script |
|------|-------------|--------|
| 1 | Export KN5 default | `export_kn5.py` |
| 2 | Setup struttura mod | `setup_mod_folder.py` |
| 3 | AI line CW | `generate_ai_line.py` |
| 4 | Generazione blend reverse | `create_reverse_blend.py` |
| 5 | Export KN5 reverse | `export_kn5.py` (TRACK_REVERSE=1) |
| 6 | AI line CCW | `generate_ai_line.py` (TRACK_REVERSE=1) |

### Build CLI (cross-platform)

`build_cli.py` esegue tutti e 6 gli step + copia i KN5 nella mod da terminale:

```bash
python build_cli.py
```

Su Linux e' disponibile anche `build.sh` che fa la stessa cosa in bash.

### Step manuali

Se si preferisce eseguire i singoli step da terminale:

```bash
# Step 1 - Export KN5
blender --background touch_and_go.blend --python scripts/export_kn5.py

# Step 2 - Setup mod folder
.venv/bin/python scripts/setup_mod_folder.py

# Step 3 - AI line CW
blender --background touch_and_go.blend --python scripts/generate_ai_line.py

# Step 4 - Reverse blend
blender --background touch_and_go.blend --python scripts/create_reverse_blend.py

# Step 5 - Export KN5 reverse
TRACK_REVERSE=1 blender --background touch_and_go_reverse.blend --python scripts/export_kn5.py

# Step 6 - AI line CCW
TRACK_REVERSE=1 blender --background touch_and_go_reverse.blend --python scripts/generate_ai_line.py

# Copy KN5 files to mod
cp touch_and_go.kn5 mod/touch_and_go/touch_and_go.kn5
cp touch_and_go_reverse.kn5 mod/touch_and_go/touch_and_go_reverse.kn5
```

## Layout in Assetto Corsa

La mod include due layout selezionabili nel menu di AC (o Content Manager):

- **Touch and Go** — senso orario (CW)
- **Touch and Go [reverse]** — senso antiorario (CCW)

La struttura multi-layout segue la convenzione ufficiale AC (come `ks_brands_hatch`):
ogni layout ha il proprio `models_<nome>.ini` nella root della pista, la propria cartella
`<nome>/` con `ai/` e `data/`, e la propria UI sotto `ui/<nome>/`.

## Installazione in Assetto Corsa

Il modo raccomandato e' usare il tab **Install** del Manager.

In alternativa su Linux e' disponibile lo script bash:

```bash
bash install.sh
# oppure con percorso AC non standard:
AC_DIR=/percorso/ad/assettocorsa bash install.sh
```

### Componenti installati

- **Touch and Go** — il circuito (copiato in `content/tracks/touch_and_go/`)
- **Content Manager** — launcher alternativo (su Linux viene impostato come launcher Steam)
- **Custom Shaders Patch** — miglioramenti grafici (dwrite.dll + extension/)
- **Font di sistema** — verdana.ttf, segoeui.ttf (solo Linux, su Windows gia' presenti)
- **Pulizia cache** — AC engine cache (ai_grids, ai_payloads, meshes_metadata) + CM cache

### Content Manager e CSP

Se mancano, scaricarli da:
- **Content Manager:** https://acstuff.ru/app/
- **CSP:** https://acstuff.club/patch/

Salvare i .zip in `addons/`, nella root del progetto, o in `~/Scaricati/` (`~/Downloads` su Windows).
L'installer (Manager o `install.sh`) li cerca automaticamente in queste posizioni; se non li trova, li scarica.

## Verifica

1. Avviare Assetto Corsa
2. Selezionare "Touch and Go" dal menu
3. Verificare:
   - L'auto parte al centro della strada, in senso orario
   - La pista si carica senza cadere nel vuoto
   - I cordoli sono nelle curve
   - Le superfici hanno il comportamento fisico corretto (asfalto, erba, cordoli)
4. Selezionare il layout "Touch and Go [reverse]" e verificare che l'auto parta in senso antiorario

## Track Viewer 3D

Viewer 3D interattivo per visualizzare i file KN5 senza aprire Assetto Corsa.

**Linux:**
```bash
source .venv/bin/activate
python tools/track_viewer.py mod/touch_and_go/touch_and_go.kn5
```
**Windows:**
```cmd
.venv\Scripts\activate
python tools\track_viewer.py mod\touch_and_go\touch_and_go.kn5
```

Controlli camera:
- **Click sinistro + drag**: orbita attorno alla pista
- **Click destro + drag**: pan
- **Rotella mouse**: zoom
- **Tasto R**: reset camera

## Struttura del progetto

```
touch-and-go-martina-franca-track/
├── touch_and_go.blend              # Sorgente Blender MASTER (geometria, materiali, empty)
├── touch_and_go_reverse.blend      # Generato automaticamente (non modificare!)
├── touch_and_go.kn5                # Modello 3D formato AC (generato)
├── touch_and_go_reverse.kn5        # Modello 3D reverse (generato)
├── centerline.json                 # Punti centerline del tracciato (79 punti, CW)
├── track_config.json               # Configurazione parametri pista
├── requirements.txt                # Dipendenze Python (numpy, Pillow, PyQt5, PyOpenGL)
├── manager.py                      # Manager GUI (build, preview, installazione)
├── build_cli.py                    # Build CLI cross-platform (6 step)
├── build.sh                        # Build CLI bash (solo Linux)
├── install.sh                      # Installazione mod + addon (solo Linux)
├── layout.png                      # Immagine sorgente del tracciato (usata come map.png)
├── cover.png                       # Immagine copertina (preview + outline in AC)
├── cordoli.png                     # Debug: mappa cordoli
├── curb_debug.png                  # Debug: tracciato cordoli su centerline
├── scripts/
│   ├── create_track.py             # Genera touch_and_go.blend da centerline.json
│   ├── create_reverse_blend.py     # Genera reverse .blend (ruota empty 180°)
│   ├── export_kn5.py               # Export KN5 da Blender (TRACK_REVERSE=1 per reverse)
│   ├── setup_mod_folder.py         # Crea struttura mod AC (default + reverse layout)
│   ├── generate_ai_line.py         # Genera AI driving line (TRACK_REVERSE=1 per CCW)
│   └── platform_utils.py           # Utility cross-platform (Blender, venv, path AC)
├── textures/
│   ├── asphalt.png                 # Texture asfalto (1024x1024)
│   ├── curb_rw.png                 # Texture cordolo rosso/bianco (256x256)
│   ├── grass.png                   # Texture erba (1024x1024)
│   ├── barrier.png                 # Texture barriera (512x512)
│   ├── startline.png               # Texture linea di partenza
│   └── reclama_banner.png          # Texture banner pubblicitario
├── tools/
│   └── track_viewer.py             # Viewer 3D per file KN5 (PyQt5 + OpenGL)
├── addons/                         # Componenti aggiuntivi per AC (CM, CSP, font)
├── builds/                         # Zip distribuibili (generati da build)
└── mod/touch_and_go/               # Mod finale pronta per AC
    ├── touch_and_go.kn5            # KN5 layout default (CW)
    ├── touch_and_go_reverse.kn5    # KN5 layout reverse (CCW)
    ├── models_default.ini          # -> touch_and_go.kn5
    ├── models_reverse.ini          # -> touch_and_go_reverse.kn5
    ├── default/                    # Layout default (CW)
    │   ├── ai/fast_lane.ai         # AI line CW
    │   ├── data/
    │   │   ├── surfaces.ini
    │   │   ├── cameras.ini
    │   │   ├── map.ini
    │   │   ├── lighting.ini
    │   │   └── groove.ini
    │   └── map.png                 # Minimap
    ├── reverse/                    # Layout reverse (CCW)
    │   ├── ai/fast_lane.ai         # AI line CCW
    │   ├── data/
    │   │   ├── surfaces.ini
    │   │   ├── cameras.ini
    │   │   ├── map.ini
    │   │   ├── lighting.ini
    │   │   └── groove.ini
    │   └── map.png                 # Minimap
    └── ui/
        ├── default/                # UI default layout
        │   ├── ui_track.json
        │   ├── preview.png
        │   └── outline.png
        └── reverse/                # UI reverse layout
            ├── ui_track.json
            ├── preview.png
            └── outline.png
```

## Dettagli tecnici

| Parametro | Valore |
|-----------|--------|
| Lunghezza | 900 m |
| Larghezza strada | 8.0 m |
| Cordoli | 1.0 m x 8 cm (solo nelle curve) |
| Erba laterale | 4 m per lato |
| Muri | 1.5 m altezza, 1.5 m spessore |
| Griglia partenza | 5 posizioni |
| Pit boxes | 5 |
| Direzione default | Orario (CW) |
| Direzione reverse | Antiorario (CCW) |
| Coordinate GPS | 40.7010, 17.3352 |
| Formato KN5 | v6, exporter custom Python |
| Texture | PNG embedded (D3DX11 auto-detect) |

## Note tecniche KN5

L'exporter KN5 custom (`scripts/export_kn5.py`) gestisce:

- **Conversione coordinate** Blender Z-up -> AC Y-up: `(x, y, z)` -> `(x, z, -y)` (det=+1, nessuna inversione winding)
- **UV V-flip** OpenGL -> DirectX: `v = 1 - v` (Blender V=0 in basso, AC V=0 in alto)
- **Empty AC_** esportati come coppie dummy+mesh (box 24 verts / 36 indices)
- **Matrice KN5**: `transpose(C * T_blender)` dove C swappa row1<->row2 con segno
- **Embedding texture** PNG direttamente (senza conversione DDS)
- **Calcolo bounding sphere** per ogni mesh
- **Matching superfici** tramite substring: KEY in `surfaces.ini` cercato nel nome mesh

### Convenzione rotazione empty (Blender -> AC)

```
rotation_euler = (+pi/2, 0, pi - heading)
```

dove `heading = atan2(tx, -ty)` con `t` = tangente della direzione di marcia in Blender.

### Reverse layout — come funziona

Il layout reverse condivide la **stessa geometria 3D** del layout default.
L'unica differenza e' la direzione degli empty `AC_START_*`, `AC_PIT_*`, `AC_TIME_*`:

1. `create_reverse_blend.py` apre `touch_and_go.blend`
2. Per ogni empty con nome che inizia con `AC_`, aggiunge `pi` (180°) alla rotazione Z
3. Salva come `touch_and_go_reverse.blend`

Questo inverte la direzione di marcia senza modificare la pista.
AC rileva i layout tramite i file `models_default.ini` e `models_reverse.ini` nella root della pista,
le cartelle `default/` e `reverse/` (con `ai/` e `data/`), e `ui/default/` e `ui/reverse/`
(convenzione Brands Hatch).

### Superfici fisiche (surfaces.ini)

| KEY | Mesh | Friction | Tipo |
|-----|------|----------|------|
| ROAD | 1ROAD | 0.97 | Pista valida |
| KERB | 1KERB_*, 2KERB_* | 0.93 | Cordoli (vibrazione) |
| GRASS | 1GRASS, 2GRASS | 0.60 | Erba (fuori pista) |
| WALL | 1WALL_SUB*, 2WALL_SUB* | 0.365 | Barriere |
| PIT | (pitlane) | 0.97 | Pit lane |
| GROUND | 1GROUND_SUB* | 0.60 | Terreno base |

## Risoluzione problemi

- **Auto parte fuori pista o capovolta:** Verificare la rotazione degli empty AC_START in Blender: deve essere `(+90, 0, angolo)`. Se e' `(-90, 0, angolo)` il Y-axis nel KN5 viene invertito.
- **Layout reverse non appare in AC:** Verificare che esistano `models_reverse.ini` nella root (punta a `touch_and_go_reverse.kn5`), `ui/reverse/ui_track.json`, e `reverse/ai/fast_lane.ai`. Pulire la cache AC e CM.
- **Auto cade nel vuoto:** Il terreno (GROUND) e i muri (WALL) devono essere suddivisi in sub-mesh con bounding sphere <30m.
- **Texture nere/mancanti:** Le texture sono embedded nel KN5 come PNG. Riesportare con `export_kn5.py`.
- **AI non funziona:** Rigenerare `fast_lane.ai` con `generate_ai_line.py`.
- **Modifiche Blender non visibili in AC:** Eseguire tutti e 6 gli step di build (Manager Build All o `python build_cli.py`), poi installare dal tab Install del Manager.
- **Banner/immagini capovolte in AC:** L'exporter deve applicare il V-flip UV (`v = 1 - v`). Riesportare.
