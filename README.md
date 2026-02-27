# Touch and Go

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![AC](https://img.shields.io/badge/assetto%20corsa-mod-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

Circuito kart a Martina Franca (TA), Puglia. 900 m, larghezza 8 m, layout CW + reverse CCW.

## Requisiti

- Python 3.10+, Blender 5.0+, Assetto Corsa (Steam)
- [blender-assetto-corsa-track-generator](../blender-assetto-corsa-track-generator/) clonato nella stessa cartella parent

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../blender-assetto-corsa-track-generator/requirements.txt
```

## Build e installazione

```bash
cd ../blender-assetto-corsa-track-generator

# Build
TRACK_ROOT=/path/to/touch-and-go-martina-franca-track python3 build_cli.py

# Build + install in AC
TRACK_ROOT=/path/to/touch-and-go-martina-franca-track python3 build_cli.py --install

# Solo install (senza rebuild)
TRACK_ROOT=/path/to/touch-and-go-martina-franca-track python3 install.py
```

## GUI Manager

```bash
cd ../blender-assetto-corsa-track-generator
source ../touch-and-go-martina-franca-track/.venv/bin/activate
python3 manager.py
```

## Struttura

```
touch_and_go.blend    Sorgente Blender
centerline.json       Dati layout v2 (road, cordoli, muri, start, map_center)
track_config.json     Configurazione pista
textures/             Texture (asphalt, curb, grass, barrier, startline, sponsor1)
cover.png             Copertina mod
```

## Parametri

| Parametro | Valore |
|-----------|--------|
| Lunghezza | 900 m |
| Larghezza | 8.0 m |
| Pit boxes | 5 |
| Layouts | CW + CCW |
| Elementi extra | Gantry startline (portale con pannello sponsor + 5 luci rosse) |
| GPS | 40.7010, 17.3352 |
