#!/bin/bash
# Touch and Go - Installazione/Aggiornamento mod per Assetto Corsa
# Installa pista, Content Manager, CSP, font
# Uso: bash install.sh

set -e

# Cerca la directory di Assetto Corsa
AC_PATHS=(
    "$HOME/.steam/steam/steamapps/common/assettocorsa"
    "$HOME/.local/share/Steam/steamapps/common/assettocorsa"
    "$HOME/.steam/debian-installation/steamapps/common/assettocorsa"
)

# Use AC_DIR from environment if already set (e.g. from manager.py)
if [ -z "$AC_DIR" ] || [ ! -d "$AC_DIR" ]; then
    AC_DIR=""
    for path in "${AC_PATHS[@]}"; do
        if [ -d "$path" ]; then
            AC_DIR="$path"
            break
        fi
    done
fi

if [ -z "$AC_DIR" ]; then
    echo "Errore: Assetto Corsa non trovato. Percorsi cercati:"
    for path in "${AC_PATHS[@]}"; do
        echo "  - $path"
    done
    echo ""
    echo "Specifica il percorso manualmente:"
    echo "  AC_DIR=/percorso/ad/assettocorsa bash install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACKS_DIR="$AC_DIR/content/tracks"

echo "=== Touch and Go - Installazione mod ==="
echo "AC trovato in: $AC_DIR"
echo ""

# --- 1. Installazione pista Touch and Go ---
MOD_NAME="touch_and_go"
MOD_FULL="$SCRIPT_DIR/mod/$MOD_NAME"
DEST="$TRACKS_DIR/$MOD_NAME"

if [ ! -d "$MOD_FULL" ]; then
    echo "Errore: cartella mod pista non trovata in $MOD_FULL"
    echo "Esegui prima la pipeline di build (bash build.sh)"
    exit 1
fi

if [ ! -f "$MOD_FULL/$MOD_NAME.kn5" ]; then
    echo "Errore: $MOD_NAME.kn5 non trovato nella cartella mod."
    echo "Esegui prima: bash build.sh"
    exit 1
fi

echo "[PISTA] Installando Touch and Go..."
if [ -d "$DEST" ]; then
    rm -rf "$DEST"
fi
cp -r "$MOD_FULL" "$DEST"
echo "[PISTA] Touch and Go installata!"

# Clean AC engine cache for this track (AI grids, payloads, mesh metadata)
AC_CACHE="$AC_DIR/cache"
if [ -d "$AC_CACHE" ]; then
    cleaned=0
    for f in "$AC_CACHE"/ai_grids/touch_and_go__* "$AC_CACHE"/ai_payloads/touch_and_go__*; do
        if [ -f "$f" ]; then
            rm -f "$f"
            cleaned=$((cleaned + 1))
        fi
    done
    # Also clean meshes_metadata (hashed names, safest to clear all)
    if [ -d "$AC_CACHE/meshes_metadata" ]; then
        rm -f "$AC_CACHE"/meshes_metadata/*.bin "$AC_CACHE"/meshes_metadata/*.tmp 2>/dev/null
        cleaned=$((cleaned + 1))
    fi
    if [ "$cleaned" -gt 0 ]; then
        echo "[CACHE] Pulita cache AC (ai_grids, ai_payloads, meshes_metadata)"
    fi
fi

# Clean Content Manager cache (Proton prefix)
CM_DATA_DIR="$HOME/.steam/steam/steamapps/compatdata/244210/pfx/drive_c/users/steamuser/AppData/Local/AcTools Content Manager"
if [ -d "$CM_DATA_DIR" ]; then
    rm -f "$CM_DATA_DIR/Cache.data" 2>/dev/null
    rm -rf "$CM_DATA_DIR/Temporary/Storages Backups" 2>/dev/null
    echo "[CACHE] Pulita cache Content Manager"
fi
echo ""

# --- 2. Content Manager ---
echo "[CM] Verifica Content Manager..."
CM_EXE="$AC_DIR/Content Manager Safe.exe"
if [ -f "$CM_EXE" ]; then
    echo "[CM] Content Manager gia' installato."
else
    # Cerca se l'utente ha scaricato il file
    CM_ZIP=""
    for f in "$SCRIPT_DIR"/addons/ContentManager*.zip "$SCRIPT_DIR"/addons/content-manager*.zip "$SCRIPT_DIR"/ContentManager*.zip "$HOME/Scaricati"/ContentManager*.zip "$HOME/Downloads"/ContentManager*.zip; do
        if [ -f "$f" ]; then
            CM_ZIP="$f"
            break
        fi
    done

    if [ -z "$CM_ZIP" ]; then
        echo "[CM] Zip non trovato, scarico da acstuff.ru..."
        mkdir -p "$SCRIPT_DIR/addons"
        CM_ZIP="$SCRIPT_DIR/addons/ContentManager.zip"
        curl -L -o "$CM_ZIP" "https://acstuff.ru/app/latest.zip"
        echo "[CM] Scaricato: $CM_ZIP"
    fi

    if [ -f "$CM_ZIP" ]; then
        echo "[CM] Trovato archivio Content Manager: $CM_ZIP"
        TMP_CM=$(mktemp -d)
        unzip -q "$CM_ZIP" -d "$TMP_CM"
        CM_FOUND=$(find "$TMP_CM" -name "Content Manager.exe" -o -name "ContentManager.exe" | head -1)
        if [ -n "$CM_FOUND" ]; then
            cp "$CM_FOUND" "$CM_EXE"
            echo "[CM] Content Manager installato in: $CM_EXE"
        else
            echo "[CM] ATTENZIONE: Content Manager.exe non trovato nell'archivio"
        fi
        rm -rf "$TMP_CM"
    fi
fi

# Replace AC launcher with Content Manager (required on Linux/Proton)
if [ -f "$CM_EXE" ]; then
    AC_LAUNCHER="$AC_DIR/AssettoCorsa.exe"
    AC_BACKUP="$AC_DIR/AssettoCorsa_original.exe"
    if [ ! -f "$AC_BACKUP" ]; then
        cp "$AC_LAUNCHER" "$AC_BACKUP"
        echo "[CM] Backup launcher originale: AssettoCorsa_original.exe"
    fi
    cp "$CM_EXE" "$AC_LAUNCHER"
    echo "[CM] Content Manager impostato come launcher di Steam"
fi
echo ""

# --- 3. Custom Shaders Patch (CSP) ---
echo "[CSP] Verifica Custom Shaders Patch..."
CSP_DLL="$AC_DIR/dwrite.dll"
CSP_EXT="$AC_DIR/extension"
if [ -f "$CSP_DLL" ] && [ -d "$CSP_EXT" ]; then
    echo "[CSP] CSP gia' installato."
else
    # Cerca archivi CSP scaricati
    CSP_ZIP=""
    for f in "$SCRIPT_DIR"/addons/lights-patch*.zip "$SCRIPT_DIR"/addons/csp*.zip "$SCRIPT_DIR"/lights-patch*.zip "$HOME/Scaricati"/lights-patch*.zip "$HOME/Downloads"/lights-patch*.zip; do
        if [ -f "$f" ]; then
            CSP_ZIP="$f"
            break
        fi
    done

    if [ -z "$CSP_ZIP" ]; then
        echo "[CSP] Zip non trovato, scarico da acstuff.club..."
        mkdir -p "$SCRIPT_DIR/addons"
        CSP_ZIP="$SCRIPT_DIR/addons/lights-patch-v0.2.11.zip"
        curl -L -o "$CSP_ZIP" "https://acstuff.club/patch/?get=0.2.11"
        echo "[CSP] Scaricato: $CSP_ZIP"
    fi

    if [ -f "$CSP_ZIP" ]; then
        echo "[CSP] Trovato archivio CSP: $CSP_ZIP"
        TMP_CSP=$(mktemp -d)
        unzip -q "$CSP_ZIP" -d "$TMP_CSP"
        if [ -f "$TMP_CSP/dwrite.dll" ]; then
            cp "$TMP_CSP/dwrite.dll" "$AC_DIR/"
            echo "[CSP] dwrite.dll copiato"
        fi
        if [ -d "$TMP_CSP/extension" ]; then
            cp -r "$TMP_CSP/extension" "$AC_DIR/"
            echo "[CSP] cartella extension/ copiata"
        fi
        rm -rf "$TMP_CSP"
        echo "[CSP] Custom Shaders Patch installato!"
    fi
fi
echo ""

# --- 4. Font Windows (necessari per CM/CSP su Linux) ---
echo "[FONT] Verifica font di sistema..."
FONTS_DIR="$AC_DIR/content/fonts/system"
if [ -f "$FONTS_DIR/verdana.ttf" ] && [ -f "$FONTS_DIR/segoeui.ttf" ]; then
    echo "[FONT] Font gia' installati."
else
    FONTS_ZIP=""
    for f in "$SCRIPT_DIR"/addons/ac-fonts.zip "$SCRIPT_DIR"/ac-fonts.zip; do
        if [ -f "$f" ]; then
            FONTS_ZIP="$f"
            break
        fi
    done

    if [ -z "$FONTS_ZIP" ]; then
        echo "[FONT] Zip non trovato, scarico da acstuff.club..."
        mkdir -p "$SCRIPT_DIR/addons"
        FONTS_ZIP="$SCRIPT_DIR/addons/ac-fonts.zip"
        curl -L -o "$FONTS_ZIP" "https://acstuff.club/u/blob/ac-fonts.zip"
        echo "[FONT] Scaricato: $FONTS_ZIP"
    fi

    if [ -f "$FONTS_ZIP" ]; then
        echo "[FONT] Trovato archivio font: $FONTS_ZIP"
        mkdir -p "$FONTS_DIR"
        unzip -o -q "$FONTS_ZIP" -d "$AC_DIR/content/fonts/"
        echo "[FONT] Font installati (verdana.ttf, segoeui.ttf)"
    fi
fi
echo ""

# --- Riepilogo ---
echo "=== Riepilogo Installazione ==="
echo ""
echo "Pista:"
if [ -d "$TRACKS_DIR/touch_and_go" ]; then
    kn5=$(find "$TRACKS_DIR/touch_and_go" -name "*.kn5" -maxdepth 1 | head -1)
    if [ -n "$kn5" ]; then
        size=$(du -h "$kn5" | cut -f1)
        echo "  [OK] Touch and Go ($size)"
    else
        echo "  [!!] Touch and Go (kn5 mancante!)"
    fi
else
    echo "  [--] Touch and Go (non installata)"
fi
echo ""

echo "Componenti aggiuntivi:"
if [ -f "$CM_EXE" ]; then
    if [ -f "$AC_DIR/AssettoCorsa_original.exe" ]; then
        echo "  [OK] Content Manager (attivo come launcher Steam)"
    else
        echo "  [OK] Content Manager (installato)"
    fi
else
    echo "  [--] Content Manager (non installato)"
fi
if [ -f "$CSP_DLL" ]; then
    echo "  [OK] Custom Shaders Patch"
else
    echo "  [--] Custom Shaders Patch (non installato)"
fi
if [ -f "$FONTS_DIR/verdana.ttf" ]; then
    echo "  [OK] Font di sistema"
else
    echo "  [--] Font di sistema (non installati)"
fi
echo ""

echo "Avvia Assetto Corsa da Steam: Content Manager partira' automaticamente."
echo "Seleziona 'Touch and Go' dal menu piste."
