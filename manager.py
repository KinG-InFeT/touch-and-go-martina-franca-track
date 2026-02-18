#!/usr/bin/env python3
"""Touch and Go Track Manager - PyQt5 pipeline manager with 3D preview."""

import glob as globmod
import json
import math
import os
import pathlib
import shutil
import struct
import sys
import tempfile

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QTextEdit, QProgressBar,
    QFileDialog, QListWidget, QListWidgetItem, QGroupBox, QCheckBox,
    QFormLayout, QDoubleSpinBox, QLineEdit, QComboBox,
    QScrollArea, QSplitter, QToolBar, QAction,
)
from PyQt5.QtCore import Qt, QTimer, QProcess, QProcessEnvironment, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QFont, QTextCursor

from OpenGL.GL import *
from OpenGL.GLU import *

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import TrackGLWidget and parse_kn5 from existing track_viewer
sys.path.insert(0, os.path.join(ROOT_DIR, "tools"))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
from track_viewer import TrackGLWidget, parse_kn5
import platform_utils


def parse_kn5_empties(path):
    """Extract AC empty (dummy node) positions from a KN5 file.
    Returns list of (name, x, y, z) for nodes whose name starts with 'AC_'."""
    empties = []

    def _rs(f):
        n = struct.unpack('<i', f.read(4))[0]
        if n < 0 or n > 10000:
            return ""
        return f.read(n).decode('utf-8', errors='replace')

    with open(path, 'rb') as f:
        magic = f.read(6)
        if magic != b'sc6969':
            return empties
        version = struct.unpack('<i', f.read(4))[0]
        if version > 5:
            f.read(4)

        # Skip textures
        for _ in range(struct.unpack('<i', f.read(4))[0]):
            struct.unpack('<i', f.read(4))  # type
            _rs(f)                          # name
            size = struct.unpack('<i', f.read(4))[0]
            f.read(size)

        # Skip materials
        for _ in range(struct.unpack('<i', f.read(4))[0]):
            _rs(f)  # name
            _rs(f)  # shader
            f.read(2)
            if version > 4:
                f.read(4)
            for _ in range(struct.unpack('<i', f.read(4))[0]):
                _rs(f); f.read(40)
            for _ in range(struct.unpack('<i', f.read(4))[0]):
                _rs(f); f.read(4); _rs(f)

        # Parse nodes
        def parse_node():
            node_type = struct.unpack('<i', f.read(4))[0]
            name = _rs(f)
            num_children = struct.unpack('<i', f.read(4))[0]
            f.read(1)  # flag

            if node_type == 1:  # Dummy
                mtx = struct.unpack('<16f', f.read(64))
                # DirectX row-major: row 3 = position = mtx[12], mtx[13], mtx[14]
                if name.startswith('AC_'):
                    empties.append((name, mtx[12], mtx[13], mtx[14]))
                for _ in range(num_children):
                    parse_node()
            elif node_type == 2:  # Mesh
                f.read(3)
                vc = struct.unpack('<i', f.read(4))[0]
                f.read(vc * 44)
                ic = struct.unpack('<i', f.read(4))[0]
                f.read(ic * 2)
                f.read(4 + 29)
                for _ in range(num_children):
                    parse_node()

        parse_node()
    return empties


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_KN5 = os.path.join(ROOT_DIR, "mod", "touch_and_go", "touch_and_go.kn5")
CONFIG_FILE = os.path.join(ROOT_DIR, "track_config.json")

DEFAULT_PARAMS = {
    "geometry": {
        "road_width": 8.0,
        "kerb_width": 1.0,
        "kerb_height": 0.08,
        "grass_width": 4.0,
        "wall_height": 1.5,
        "wall_thickness": 1.5,
    },
    "ai_line": {
        "default_speed": 75.0,
        "min_corner_speed": 35.0,
    },
    "surfaces": {
        "road_friction": 0.97,
        "kerb_friction": 0.93,
        "grass_friction": 0.60,
    },
    "info": {
        "name": "Touch and Go",
        "city": "Martina Franca",
        "country": "Italy",
        "length": "900",
        "pitboxes": "5",
        "direction": "clockwise",
    },
}

BLENDER = platform_utils.find_blender()

_BLEND = os.path.join(ROOT_DIR, "touch_and_go.blend")
_BLEND_REV = os.path.join(ROOT_DIR, "touch_and_go_reverse.blend")

BUILD_STEPS = [
    ("1 - Export KN5", [BLENDER, "--background", _BLEND, "--python",
                        os.path.join(ROOT_DIR, "scripts", "export_kn5.py")]),
    ("2 - Mod folder", [platform_utils.venv_python(),
                        os.path.join(ROOT_DIR, "scripts", "setup_mod_folder.py")]),
    ("3 - AI line CW", [BLENDER, "--background", _BLEND, "--python",
                         os.path.join(ROOT_DIR, "scripts", "generate_ai_line.py")]),
    ("4 - Reverse blend", [BLENDER, "--background", _BLEND, "--python",
                            os.path.join(ROOT_DIR, "scripts", "create_reverse_blend.py")]),
    ("5 - KN5 reverse", [BLENDER, "--background", _BLEND_REV, "--python",
                          os.path.join(ROOT_DIR, "scripts", "export_kn5.py")]),
    ("6 - AI line CCW", [BLENDER, "--background", _BLEND_REV, "--python",
                          os.path.join(ROOT_DIR, "scripts", "generate_ai_line.py")]),
]

AC_SEARCH_PATHS = platform_utils.ac_search_paths()

LOG_TERM_STYLE = (
    "QTextEdit { background: #1e1e1e; color: #dcdcdc; "
    "font-family: Monospace; font-size: 9pt; border: none; }"
)


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(35, 35, 38))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(55, 55, 58))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)


# ---------------------------------------------------------------------------
# Extended GL Widget with start marker + ray-casting
# ---------------------------------------------------------------------------

class ManagerGLWidget(TrackGLWidget):
    """TrackGLWidget with empties rendering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.empties = []            # [(name, x, y, z), ...]

    def reset_camera(self):
        self.cam_target = self._scene_center.copy()
        self.cam_dist = self._scene_radius * 2.5
        self.cam_yaw = 90.0   # camera from +Z side: screen-up = -display_Z = +Blender_Y
        self.cam_pitch = 60.0
        self.update()

    # -- rendering --

    def paintGL(self):
        super().paintGL()
        self._draw_empties()

    def _draw_empties(self):
        """Draw AC empties: START=green, PIT=blue, TIME=yellow, HOTLAP=cyan."""
        if not self.empties:
            return

        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_DEPTH_TEST)

        for name, x, y, z in self.empties:
            if 'START' in name:
                glColor4f(0.2, 1.0, 0.3, 1.0)
            elif 'PIT' in name:
                glColor4f(0.3, 0.5, 1.0, 1.0)
            elif 'TIME' in name:
                glColor4f(1.0, 1.0, 0.2, 1.0)
            else:
                glColor4f(0.0, 0.9, 0.9, 1.0)

            # Filled circle on ground
            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(x, y + 0.1, z)
            r = 0.7
            for i in range(17):
                a = 2.0 * math.pi * i / 16
                glVertex3f(x + r * math.cos(a), y + 0.1, z + r * math.sin(a))
            glEnd()

            # Vertical stick
            glLineWidth(2.0)
            glBegin(GL_LINES)
            glVertex3f(x, y + 0.1, z)
            glVertex3f(x, y + 2.5, z)
            glEnd()

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glLineWidth(1.0)



# ---------------------------------------------------------------------------
# Tab 1: Preview 3D
# ---------------------------------------------------------------------------

class PreviewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""

        # GL widget (extended)
        self.gl_widget = ManagerGLWidget()

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)

        btn_open = QPushButton("Apri KN5...")
        btn_open.clicked.connect(self._open_file)
        sidebar_layout.addWidget(btn_open)

        btn_reload = QPushButton("Ricarica")
        btn_reload.clicked.connect(self.reload)
        sidebar_layout.addWidget(btn_reload)

        btn_reset = QPushButton("Reset Camera (R)")
        btn_reset.clicked.connect(self.gl_widget.reset_camera)
        sidebar_layout.addWidget(btn_reset)

        # Camera group
        cam_group = QGroupBox("Camera")
        cam_layout = QVBoxLayout(cam_group)
        btn_save_cam = QPushButton("Salva Camera")
        btn_save_cam.clicked.connect(self._save_camera)
        cam_layout.addWidget(btn_save_cam)
        btn_load_cam = QPushButton("Carica Camera")
        btn_load_cam.clicked.connect(self._load_camera)
        cam_layout.addWidget(btn_load_cam)
        self.cam_status = QLabel("")
        self.cam_status.setWordWrap(True)
        self.cam_status.setStyleSheet("font-size: 8pt;")
        cam_layout.addWidget(self.cam_status)
        sidebar_layout.addWidget(cam_group)

        # Mesh group
        mesh_group = QGroupBox("Mesh")
        mesh_layout = QVBoxLayout(mesh_group)
        self.mesh_list = QListWidget()
        self.mesh_list.itemChanged.connect(self._on_mesh_toggled)
        mesh_layout.addWidget(self.mesh_list)
        sidebar_layout.addWidget(mesh_group, stretch=1)

        info_group = QGroupBox("Info")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("Nessun file caricato")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        sidebar_layout.addWidget(info_group)

        # Main layout with splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self.gl_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open KN5 file", ROOT_DIR,
            "KN5 files (*.kn5);;All files (*)")
        if path:
            self._load_kn5(path)

    def reload(self):
        if self._current_file and os.path.isfile(self._current_file):
            self._load_kn5(self._current_file)
        elif os.path.isfile(DEFAULT_KN5):
            self._load_kn5(DEFAULT_KN5)
        self._load_camera()

    def _load_kn5(self, path):
        QApplication.processEvents()
        try:
            textures, materials, meshes = parse_kn5(path)
        except Exception as e:
            self.info_label.setText(f"Errore: {e}")
            return

        self._current_file = path
        self.gl_widget.load_scene(textures, materials, meshes)

        # Load AC empties (display coords = AC coords, no conversion)
        try:
            raw = parse_kn5_empties(path)
            self.gl_widget.empties = list(raw)
        except Exception:
            self.gl_widget.empties = []

        # Mesh list
        self.mesh_list.blockSignals(True)
        self.mesh_list.clear()
        for m in meshes:
            item = QListWidgetItem(f"{m['name']} ({m['tri_count']} tri)")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, m['name'])
            self.mesh_list.addItem(item)
        self.mesh_list.blockSignals(False)

        # Info
        total_verts = sum(len(m['verts']) for m in meshes)
        total_tris = sum(m['tri_count'] for m in meshes)
        self.info_label.setText(
            f"File: {os.path.basename(path)}\n"
            f"Mesh: {len(meshes)}\n"
            f"Vertici: {total_verts:,}\n"
            f"Triangoli: {total_tris:,}\n"
            f"Texture: {len(textures)}\n"
            f"Materiali: {len(materials)}"
        )

    def _on_mesh_toggled(self, item):
        mesh_name = item.data(Qt.UserRole)
        visible = item.checkState() == Qt.Checked
        self.gl_widget.mesh_visible[mesh_name] = visible
        self.gl_widget.update()

    # -- camera save/load --

    def _save_camera(self):
        gl = self.gl_widget
        cam_data = {
            "yaw": gl.cam_yaw,
            "pitch": gl.cam_pitch,
            "distance": gl.cam_dist,
            "target": [float(gl.cam_target[0]),
                       float(gl.cam_target[1]),
                       float(gl.cam_target[2])],
        }
        config = {}
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    config = json.load(f)
            except Exception:
                pass
        config["camera"] = cam_data
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        self.cam_status.setText(
            f"Salvata: yaw={gl.cam_yaw:.1f} pitch={gl.cam_pitch:.1f}\n"
            f"dist={gl.cam_dist:.1f}"
        )
        self.cam_status.setStyleSheet("font-size: 8pt; color: #55cc55;")

    def _load_camera(self):
        if not os.path.isfile(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
        except Exception:
            return
        cam = config.get("camera")
        if not cam:
            return
        gl = self.gl_widget
        gl.cam_yaw = cam.get("yaw", gl.cam_yaw)
        gl.cam_pitch = cam.get("pitch", gl.cam_pitch)
        gl.cam_dist = cam.get("distance", gl.cam_dist)
        t = cam.get("target")
        if t and len(t) == 3:
            gl.cam_target[0] = t[0]
            gl.cam_target[1] = t[1]
            gl.cam_target[2] = t[2]
        gl._update_projection()
        gl.update()
        self.cam_status.setText(
            f"Caricata: yaw={gl.cam_yaw:.1f} pitch={gl.cam_pitch:.1f}\n"
            f"dist={gl.cam_dist:.1f}"
        )
        self.cam_status.setStyleSheet("font-size: 8pt; color: #5599ff;")



# ---------------------------------------------------------------------------
# Tab 2: Build
# ---------------------------------------------------------------------------

class BuildTab(QWidget):
    def __init__(self, preview_tab, main_window, parent=None):
        super().__init__(parent)
        self.preview_tab = preview_tab
        self.main_window = main_window
        self._process = None
        self._queue = []       # indices into BUILD_STEPS
        self._current_step = -1

        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_build_all = QPushButton("Build All")
        self.btn_build_all.setStyleSheet(
            "QPushButton { background: #2a6e2a; padding: 6px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #358535; }"
        )
        self.btn_build_all.clicked.connect(self._build_all)
        toolbar.addWidget(self.btn_build_all)

        self.step_buttons = []
        for i, (label, _cmd) in enumerate(BUILD_STEPS):
            btn = QPushButton(f"Step {i + 1}")
            btn.setToolTip(label)
            btn.clicked.connect(lambda checked, idx=i: self._build_single(idx))
            toolbar.addWidget(btn)
            self.step_buttons.append(btn)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setStyleSheet(
            "QPushButton { background: #8b2020; padding: 6px 12px; }"
            "QPushButton:hover { background: #a52a2a; }"
        )
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        toolbar.addWidget(self.btn_stop)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Progress
        prog_layout = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, len(BUILD_STEPS))
        self.progress.setValue(0)
        prog_layout.addWidget(self.progress)
        self.status_label = QLabel("Pronto")
        self.status_label.setMinimumWidth(200)
        prog_layout.addWidget(self.status_label)
        layout.addLayout(prog_layout)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(LOG_TERM_STYLE)
        layout.addWidget(self.log)

    def _append_log(self, text, color="#dcdcdc"):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(
            f'<span style="color:{color};">{text}</span><br>'
        )
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def _set_running(self, running):
        self.btn_build_all.setEnabled(not running)
        for btn in self.step_buttons:
            btn.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def _build_all(self):
        self.log.clear()
        self.progress.setValue(0)
        self._queue = list(range(len(BUILD_STEPS)))
        self._set_running(True)
        self._run_next()

    def _build_single(self, idx):
        self.log.clear()
        self.progress.setValue(0)
        self.progress.setRange(0, 1)
        self._queue = [idx]
        self._set_running(True)
        self._run_next()

    def _run_next(self):
        if not self._queue:
            self._on_all_done()
            return

        step_idx = self._queue.pop(0)
        self._current_step = step_idx
        label, cmd = BUILD_STEPS[step_idx]

        self._append_log(f"{'=' * 60}", "#5599ff")
        self._append_log(f"  Step {step_idx + 1}: {label}", "#5599ff")
        self._append_log(f"{'=' * 60}", "#5599ff")
        self.status_label.setText(f"Step {step_idx + 1}: {label}")

        self._process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        venv_bin = platform_utils.venv_bin_dir()
        env.insert("PATH", venv_bin + platform_utils.path_separator() + env.value("PATH"))
        # Steps 5 and 6 (reverse KN5 + reverse AI) need TRACK_REVERSE=1
        if step_idx >= 4:
            env.insert("TRACK_REVERSE", "1")
        self._process.setProcessEnvironment(env)
        self._process.setWorkingDirectory(ROOT_DIR)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_step_finished)

        program = cmd[0]
        args = cmd[1:]
        self._process.start(program, args)

    def _on_stdout(self):
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            self._append_log(line, "#dcdcdc")

    def _on_stderr(self):
        data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            self._append_log(line, "#e8a838")

    def _on_step_finished(self, exit_code, _exit_status):
        step_idx = self._current_step
        label = BUILD_STEPS[step_idx][0] if 0 <= step_idx < len(BUILD_STEPS) else "?"

        if exit_code == 0:
            self._append_log(f"  v {label} completato", "#55cc55")
            # Update progress based on completed steps
            done = len(BUILD_STEPS) - len(self._queue)
            if self.progress.maximum() == len(BUILD_STEPS):
                self.progress.setValue(done)
            else:
                self.progress.setValue(1)
        else:
            self._append_log(f"  x {label} fallito (exit code {exit_code})", "#ff5555")
            self._queue.clear()
            self._set_running(False)
            self.status_label.setText(f"Errore nello step {step_idx + 1}")
            return

        self._process = None
        self._run_next()

    def _on_all_done(self):
        self._set_running(False)
        self.status_label.setText("Build completata!")
        self._append_log("", "#55cc55")
        self._append_log("Build completata!", "#55cc55")

        # Copy KN5 files to mod folder
        mod_dir = os.path.dirname(DEFAULT_KN5)
        os.makedirs(mod_dir, exist_ok=True)
        for kn5_name in ["touch_and_go.kn5", "touch_and_go_reverse.kn5"]:
            src = os.path.join(ROOT_DIR, kn5_name)
            dst = os.path.join(mod_dir, kn5_name)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                self._append_log(f"{kn5_name} copiato in mod/", "#55cc55")

        # Reload preview and switch tab
        self.preview_tab.reload()
        self.main_window.tabs.setCurrentIndex(0)

    def _stop(self):
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.kill()
        self._queue.clear()
        self._set_running(False)
        self.status_label.setText("Interrotto")
        self._append_log("Build interrotta dall'utente.", "#ff5555")


# ---------------------------------------------------------------------------
# Tab 3: Install
# ---------------------------------------------------------------------------

class InstallWorker(QThread):
    """Background worker for cross-platform installation (no bash dependency)."""
    log_message = pyqtSignal(str, str)  # (text, color)
    finished_signal = pyqtSignal(bool)  # success

    def __init__(self, ac_dir, components, parent=None):
        super().__init__(parent)
        self.ac_dir = ac_dir
        self.components = components  # dict of component_name -> bool

    def _log(self, text, color="#dcdcdc"):
        self.log_message.emit(text, color)

    def run(self):
        ok = True
        try:
            if self.components.get("track"):
                self._install_track()
            if self.components.get("clean_cache"):
                self._clean_caches()
            if self.components.get("cm"):
                self._install_cm()
            if self.components.get("csp"):
                self._install_csp()
            if self.components.get("fonts") and platform_utils.IS_LINUX:
                self._install_fonts()
            self._log("", "#55cc55")
            self._log("=== Installazione completata! ===", "#55cc55")
        except Exception as e:
            self._log(f"Errore: {e}", "#ff5555")
            ok = False
        self.finished_signal.emit(ok)

    def _install_track(self):
        self._log("=== Installazione pista ===", "#5599ff")
        mod_src = os.path.join(ROOT_DIR, "mod", "touch_and_go")
        kn5_file = os.path.join(mod_src, "touch_and_go.kn5")
        if not os.path.isdir(mod_src):
            self._log("Errore: cartella mod/touch_and_go non trovata. Esegui prima la build.", "#ff5555")
            return
        if not os.path.isfile(kn5_file):
            self._log("Errore: touch_and_go.kn5 non trovato nella cartella mod.", "#ff5555")
            return
        dest = os.path.join(self.ac_dir, "content", "tracks", "touch_and_go")
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(mod_src, dest)
        self._log("[PISTA] Touch and Go installata!", "#55cc55")

    def _clean_caches(self):
        self._log("=== Pulizia cache ===", "#5599ff")
        cleaned = 0
        # AC engine caches
        ac_cache = os.path.join(self.ac_dir, "cache")
        if os.path.isdir(ac_cache):
            for subdir in ("ai_grids", "ai_payloads"):
                pattern = os.path.join(ac_cache, subdir, "touch_and_go__*")
                for f in globmod.glob(pattern):
                    os.remove(f)
                    cleaned += 1
            mesh_meta = os.path.join(ac_cache, "meshes_metadata")
            if os.path.isdir(mesh_meta):
                for f in globmod.glob(os.path.join(mesh_meta, "*.bin")):
                    os.remove(f)
                    cleaned += 1
                for f in globmod.glob(os.path.join(mesh_meta, "*.tmp")):
                    os.remove(f)
                    cleaned += 1
        # Content Manager cache
        cm_dir = platform_utils.cm_cache_dir()
        if cm_dir and os.path.isdir(cm_dir):
            cache_data = os.path.join(cm_dir, "Cache.data")
            if os.path.isfile(cache_data):
                os.remove(cache_data)
                cleaned += 1
            backups = os.path.join(cm_dir, "Temporary", "Storages Backups")
            if os.path.isdir(backups):
                shutil.rmtree(backups)
                cleaned += 1
        if cleaned > 0:
            self._log(f"[CACHE] Pulita cache AC e CM ({cleaned} elementi)", "#55cc55")
        else:
            self._log("[CACHE] Nessuna cache da pulire", "#dcdcdc")

    def _find_addon_zip(self, patterns):
        """Search for a zip file matching glob patterns in addons/ and Downloads."""
        search_dirs = [os.path.join(ROOT_DIR, "addons"), ROOT_DIR]
        search_dirs.extend(platform_utils.download_dir_candidates())
        for d in search_dirs:
            for pat in patterns:
                for f in globmod.glob(os.path.join(d, pat)):
                    if os.path.isfile(f):
                        return f
        return None

    def _install_cm(self):
        self._log("=== Content Manager ===", "#5599ff")
        cm_exe = os.path.join(self.ac_dir, "Content Manager Safe.exe")
        if os.path.isfile(cm_exe):
            self._log("[CM] Content Manager gia' installato.", "#dcdcdc")
        else:
            cm_zip = self._find_addon_zip(["ContentManager*.zip", "content-manager*.zip"])
            if not cm_zip:
                self._log("[CM] Zip non trovato, scarico da acstuff.ru...", "#e8a838")
                addons_dir = os.path.join(ROOT_DIR, "addons")
                os.makedirs(addons_dir, exist_ok=True)
                cm_zip = os.path.join(addons_dir, "ContentManager.zip")
                if not platform_utils.download_file("https://acstuff.ru/app/latest.zip", cm_zip):
                    self._log("[CM] Download fallito!", "#ff5555")
                    return
                self._log(f"[CM] Scaricato: {cm_zip}", "#dcdcdc")
            # Extract and find exe
            self._log(f"[CM] Estrazione da: {os.path.basename(cm_zip)}", "#dcdcdc")
            tmp_dir = tempfile.mkdtemp()
            try:
                if not platform_utils.extract_zip(cm_zip, tmp_dir):
                    self._log("[CM] Estrazione fallita!", "#ff5555")
                    return
                cm_found = None
                for root, _dirs, files in os.walk(tmp_dir):
                    for fn in files:
                        if fn.lower() in ("content manager.exe", "contentmanager.exe"):
                            cm_found = os.path.join(root, fn)
                            break
                    if cm_found:
                        break
                if cm_found:
                    shutil.copy2(cm_found, cm_exe)
                    self._log(f"[CM] Content Manager installato!", "#55cc55")
                else:
                    self._log("[CM] Content Manager.exe non trovato nell'archivio", "#ff5555")
                    return
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        # Replace AC launcher with CM (required on Linux/Proton)
        if os.path.isfile(cm_exe) and platform_utils.IS_LINUX:
            ac_launcher = os.path.join(self.ac_dir, "AssettoCorsa.exe")
            ac_backup = os.path.join(self.ac_dir, "AssettoCorsa_original.exe")
            if os.path.isfile(ac_launcher) and not os.path.isfile(ac_backup):
                shutil.copy2(ac_launcher, ac_backup)
                self._log("[CM] Backup launcher originale: AssettoCorsa_original.exe", "#dcdcdc")
            if os.path.isfile(ac_launcher):
                shutil.copy2(cm_exe, ac_launcher)
                self._log("[CM] CM impostato come launcher Steam", "#55cc55")

    def _install_csp(self):
        self._log("=== Custom Shaders Patch ===", "#5599ff")
        csp_dll = os.path.join(self.ac_dir, "dwrite.dll")
        csp_ext = os.path.join(self.ac_dir, "extension")
        if os.path.isfile(csp_dll) and os.path.isdir(csp_ext):
            self._log("[CSP] CSP gia' installato.", "#dcdcdc")
            return
        csp_zip = self._find_addon_zip(["lights-patch*.zip", "csp*.zip"])
        if not csp_zip:
            self._log("[CSP] Zip non trovato, scarico da acstuff.club...", "#e8a838")
            addons_dir = os.path.join(ROOT_DIR, "addons")
            os.makedirs(addons_dir, exist_ok=True)
            csp_zip = os.path.join(addons_dir, "lights-patch-v0.2.11.zip")
            if not platform_utils.download_file("https://acstuff.club/patch/?get=0.2.11", csp_zip):
                self._log("[CSP] Download fallito!", "#ff5555")
                return
            self._log(f"[CSP] Scaricato: {csp_zip}", "#dcdcdc")
        self._log(f"[CSP] Estrazione da: {os.path.basename(csp_zip)}", "#dcdcdc")
        tmp_dir = tempfile.mkdtemp()
        try:
            if not platform_utils.extract_zip(csp_zip, tmp_dir):
                self._log("[CSP] Estrazione fallita!", "#ff5555")
                return
            dll_src = os.path.join(tmp_dir, "dwrite.dll")
            ext_src = os.path.join(tmp_dir, "extension")
            if os.path.isfile(dll_src):
                shutil.copy2(dll_src, self.ac_dir)
                self._log("[CSP] dwrite.dll copiato", "#dcdcdc")
            if os.path.isdir(ext_src):
                dest_ext = os.path.join(self.ac_dir, "extension")
                if os.path.isdir(dest_ext):
                    shutil.rmtree(dest_ext)
                shutil.copytree(ext_src, dest_ext)
                self._log("[CSP] cartella extension/ copiata", "#dcdcdc")
            self._log("[CSP] Custom Shaders Patch installato!", "#55cc55")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _install_fonts(self):
        self._log("=== Font di sistema ===", "#5599ff")
        fonts_dir = os.path.join(self.ac_dir, "content", "fonts", "system")
        verdana = os.path.join(fonts_dir, "verdana.ttf")
        segoeui = os.path.join(fonts_dir, "segoeui.ttf")
        if os.path.isfile(verdana) and os.path.isfile(segoeui):
            self._log("[FONT] Font gia' installati.", "#dcdcdc")
            return
        fonts_zip = self._find_addon_zip(["ac-fonts.zip"])
        if not fonts_zip:
            self._log("[FONT] Zip non trovato, scarico da acstuff.club...", "#e8a838")
            addons_dir = os.path.join(ROOT_DIR, "addons")
            os.makedirs(addons_dir, exist_ok=True)
            fonts_zip = os.path.join(addons_dir, "ac-fonts.zip")
            if not platform_utils.download_file("https://acstuff.club/u/blob/ac-fonts.zip", fonts_zip):
                self._log("[FONT] Download fallito!", "#ff5555")
                return
            self._log(f"[FONT] Scaricato: {fonts_zip}", "#dcdcdc")
        fonts_base = os.path.join(self.ac_dir, "content", "fonts")
        os.makedirs(fonts_base, exist_ok=True)
        if platform_utils.extract_zip(fonts_zip, fonts_base):
            self._log("[FONT] Font installati!", "#55cc55")
        else:
            self._log("[FONT] Estrazione fallita!", "#ff5555")


class InstallTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._ac_dir = self._detect_ac()

        layout = QVBoxLayout(self)

        # AC path
        path_group = QGroupBox("Percorso Assetto Corsa")
        path_layout = QHBoxLayout(path_group)
        self.path_label = QLabel(self._ac_dir or "Non trovato")
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label, stretch=1)
        btn_browse = QPushButton("Cambia percorso...")
        btn_browse.clicked.connect(self._browse_ac)
        path_layout.addWidget(btn_browse)
        layout.addWidget(path_group)

        # Component checkboxes
        comp_group = QGroupBox("Componenti da installare")
        comp_layout = QVBoxLayout(comp_group)
        self.chk_track = QCheckBox("Touch and Go")
        self.chk_track.setChecked(True)
        comp_layout.addWidget(self.chk_track)
        self.chk_cache = QCheckBox("Pulisci cache AC e CM")
        self.chk_cache.setChecked(True)
        comp_layout.addWidget(self.chk_cache)
        self.chk_cm = QCheckBox("Content Manager")
        self.chk_cm.setChecked(True)
        comp_layout.addWidget(self.chk_cm)
        self.chk_csp = QCheckBox("Custom Shaders Patch (CSP)")
        self.chk_csp.setChecked(True)
        comp_layout.addWidget(self.chk_csp)
        self.chk_fonts = QCheckBox("Font di sistema (solo Linux)")
        self.chk_fonts.setChecked(platform_utils.IS_LINUX)
        self.chk_fonts.setEnabled(platform_utils.IS_LINUX)
        comp_layout.addWidget(self.chk_fonts)
        layout.addWidget(comp_group)

        # Install button
        btn_layout = QHBoxLayout()
        self.btn_install = QPushButton("Installa")
        self.btn_install.setStyleSheet(
            "QPushButton { background: #2a6e2a; padding: 8px 24px; font-weight: bold; font-size: 11pt; }"
            "QPushButton:hover { background: #358535; }"
        )
        self.btn_install.clicked.connect(self._install)
        btn_layout.addWidget(self.btn_install)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(LOG_TERM_STYLE)
        layout.addWidget(self.log)

    def _detect_ac(self):
        env_dir = os.environ.get("AC_DIR")
        if env_dir and os.path.isdir(env_dir):
            return env_dir
        for path in AC_SEARCH_PATHS:
            if os.path.isdir(path):
                return path
        return ""

    def _browse_ac(self):
        d = QFileDialog.getExistingDirectory(self, "Seleziona cartella Assetto Corsa", "")
        if d:
            self._ac_dir = d
            self.path_label.setText(d)

    def _append_log(self, text, color="#dcdcdc"):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(
            f'<span style="color:{color};">{text}</span><br>'
        )
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def _install(self):
        if not self._ac_dir:
            self._append_log("Errore: nessun percorso AC selezionato!", "#ff5555")
            return

        self.log.clear()
        self.btn_install.setEnabled(False)
        self._append_log(f"Installazione in: {self._ac_dir}", "#5599ff")

        components = {
            "track": self.chk_track.isChecked(),
            "clean_cache": self.chk_cache.isChecked(),
            "cm": self.chk_cm.isChecked(),
            "csp": self.chk_csp.isChecked(),
            "fonts": self.chk_fonts.isChecked(),
        }

        self._worker = InstallWorker(self._ac_dir, components)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success):
        self.btn_install.setEnabled(True)
        if not success:
            self._append_log("Installazione fallita!", "#ff5555")
        self._worker = None


# ---------------------------------------------------------------------------
# Tab 4: Parameters
# ---------------------------------------------------------------------------

PARAM_DEFS = {
    "geometry": {
        "label": "Geometria",
        "params": [
            ("road_width",     "Road Width (m)",      "double", 8.0,  3.0,  20.0, 0.5),
            ("kerb_width",     "Kerb Width (m)",      "double", 1.0,  0.2,  3.0,  0.1),
            ("kerb_height",    "Kerb Height (m)",     "double", 0.08, 0.01, 0.3,  0.01),
            ("grass_width",    "Grass Width (m)",     "double", 4.0,  1.0,  50.0, 1.0),
            ("wall_height",    "Wall Height (m)",     "double", 1.5,  0.5,  5.0,  0.1),
            ("wall_thickness", "Wall Thickness (m)",  "double", 1.5,  0.3,  3.0,  0.1),
        ],
    },
    "ai_line": {
        "label": "AI Line",
        "params": [
            ("default_speed",    "Default Speed (km/h)",    "double", 75.0, 20.0, 200.0, 5.0),
            ("min_corner_speed", "Min Corner Speed (km/h)", "double", 35.0, 10.0, 100.0, 5.0),
        ],
    },
    "surfaces": {
        "label": "Superfici",
        "params": [
            ("road_friction", "Road Friction",  "double", 0.97, 0.5, 1.0, 0.01),
            ("kerb_friction", "Kerb Friction",  "double", 0.93, 0.5, 1.0, 0.01),
            ("grass_friction","Grass Friction",  "double", 0.60, 0.1, 1.0, 0.01),
        ],
    },
}

INFO_FIELDS = [
    ("name",      "Name",      "line",  "Touch and Go"),
    ("city",      "City",      "line",  "Martina Franca"),
    ("country",   "Country",   "line",  "Italy"),
    ("length",    "Length (m)", "line",  "900"),
    ("pitboxes",  "Pitboxes",  "line",  "5"),
    ("direction", "Direction", "combo", "clockwise"),
]


class ParametersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets = {}  # key -> widget

        main_layout = QVBoxLayout(self)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Salva")
        btn_save.setStyleSheet(
            "QPushButton { background: #2a6e2a; padding: 6px 16px; }"
            "QPushButton:hover { background: #358535; }"
        )
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)

        btn_load = QPushButton("Carica")
        btn_load.clicked.connect(self._load)
        btn_layout.addWidget(btn_load)

        btn_defaults = QPushButton("Ripristina Defaults")
        btn_defaults.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(btn_defaults)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Numeric parameter groups
        for group_key, group_def in PARAM_DEFS.items():
            group_box = QGroupBox(group_def["label"])
            form = QFormLayout(group_box)
            for key, label, _type, default, vmin, vmax, step in group_def["params"]:
                spin = QDoubleSpinBox()
                spin.setRange(vmin, vmax)
                spin.setSingleStep(step)
                spin.setDecimals(2)
                spin.setValue(default)
                form.addRow(label, spin)
                self._widgets[f"{group_key}.{key}"] = spin
            scroll_layout.addWidget(group_box)

        # Info group
        info_box = QGroupBox("Info")
        info_form = QFormLayout(info_box)
        for key, label, wtype, default in INFO_FIELDS:
            if wtype == "combo":
                widget = QComboBox()
                widget.addItems(["clockwise", "counter-clockwise"])
                widget.setCurrentText(default)
            else:
                widget = QLineEdit(default)
            info_form.addRow(label, widget)
            self._widgets[f"info.{key}"] = widget
        scroll_layout.addWidget(info_box)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Status
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

        # Auto-load if config exists
        if os.path.isfile(CONFIG_FILE):
            QTimer.singleShot(100, self._load)

    def _get_values(self):
        data = {}
        for group_key, group_def in PARAM_DEFS.items():
            data[group_key] = {}
            for key, _label, _type, _default, _vmin, _vmax, _step in group_def["params"]:
                widget = self._widgets[f"{group_key}.{key}"]
                data[group_key][key] = widget.value()

        data["info"] = {}
        for key, _label, wtype, _default in INFO_FIELDS:
            widget = self._widgets[f"info.{key}"]
            if wtype == "combo":
                data["info"][key] = widget.currentText()
            else:
                data["info"][key] = widget.text()
        return data

    def _set_values(self, data):
        for group_key, group_def in PARAM_DEFS.items():
            group_data = data.get(group_key, {})
            for key, _label, _type, _default, _vmin, _vmax, _step in group_def["params"]:
                if key in group_data:
                    self._widgets[f"{group_key}.{key}"].setValue(group_data[key])

        info_data = data.get("info", {})
        for key, _label, wtype, _default in INFO_FIELDS:
            if key in info_data:
                widget = self._widgets[f"info.{key}"]
                if wtype == "combo":
                    widget.setCurrentText(info_data[key])
                else:
                    widget.setText(str(info_data[key]))

    def _save(self):
        data = self._get_values()
        # Merge with existing config to preserve camera settings
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    existing = json.load(f)
                for k, v in existing.items():
                    if k not in data:
                        data[k] = v
            except Exception:
                pass
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self.status_label.setText(f"Salvato: {CONFIG_FILE}")
            self.status_label.setStyleSheet("color: #55cc55;")
        except Exception as e:
            self.status_label.setText(f"Errore: {e}")
            self.status_label.setStyleSheet("color: #ff5555;")

    def _load(self):
        if not os.path.isfile(CONFIG_FILE):
            self.status_label.setText("File non trovato")
            self.status_label.setStyleSheet("color: #e8a838;")
            return
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            self._set_values(data)
            self.status_label.setText("Parametri caricati")
            self.status_label.setStyleSheet("color: #55cc55;")
        except Exception as e:
            self.status_label.setText(f"Errore: {e}")
            self.status_label.setStyleSheet("color: #ff5555;")

    def _reset_defaults(self):
        self._set_values(DEFAULT_PARAMS)
        self.status_label.setText("Defaults ripristinati")
        self.status_label.setStyleSheet("color: #5599ff;")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class TrackManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Touch and Go - Track Manager")
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: Preview
        self.preview_tab = PreviewTab()
        self.tabs.addTab(self.preview_tab, "Preview 3D")

        # Tab 2: Build
        self.build_tab = BuildTab(self.preview_tab, self)
        self.tabs.addTab(self.build_tab, "Build")

        # Tab 3: Install
        self.install_tab = InstallTab()
        self.tabs.addTab(self.install_tab, "Install")

        # Tab 4: Parameters
        self.params_tab = ParametersTab()
        self.tabs.addTab(self.params_tab, "Parametri")

        self.statusBar().showMessage("Pronto")

        # Auto-export KN5 on startup so preview matches Blender
        QTimer.singleShot(300, self._auto_export_kn5)

    def _auto_export_kn5(self):
        blend = os.path.join(ROOT_DIR, "touch_and_go.blend")
        if os.path.isfile(blend):
            self.tabs.setCurrentIndex(1)  # switch to Build tab
            self.build_tab._build_single(0)  # run step 1: Export KN5


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = TrackManager()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
