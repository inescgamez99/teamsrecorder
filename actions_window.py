"""
Ventana pequeña y limpia solo para acciones ejecutables.
Reemplaza la UI grande de actions_ui.py para el flujo post-reunión.
"""
import logging
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from config import PROJECT_DIR

log = logging.getLogger(__name__)

_CLAUDE_EXE = r'C:\Users\ines.campos\.local\bin\claude.exe'
_CLAUDE_BIN = _CLAUDE_EXE if Path(_CLAUDE_EXE).exists() else shutil.which('claude')
CLAUDE_PROJECTS_DIR = PROJECT_DIR.parent

_PWSH = next(
    (p for p in [
        r'C:\Program Files\PowerShell\7\pwsh.exe',
        shutil.which('pwsh'),
    ] if p and Path(p).exists()),
    'powershell'
)

# Paleta clara y limpia
_BG      = '#ffffff'
_SURFACE = '#f8f9fc'
_BORDER  = '#e5e7eb'
_TEXT    = '#1a1a2e'
_SUBTEXT = '#6b7280'
_ACCENT  = '#667eea'
_GREEN   = '#22c55e'
_GREEN_BG= '#f0fdf4'
_YELLOW  = '#f59e0b'
_YELLOW_BG='#fff8e6'

TYPE_ICONS = {
    'instruction':    '⚡',
    'code_change':    '💻',
    'document_change':'📄',
}


class ActionsWindow:
    def __init__(self, minutes_path: Path):
        self.minutes_path = minutes_path
        self.root = tk.Tk()
        self.root.title('Acciones de la reunión')
        self.root.configure(bg=_BG)
        self.root.geometry('560x680')
        self.root.resizable(True, True)
        self._actions: list[dict] = []
        self._build_ui()
        self._load_actions()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=_ACCENT, pady=14)
        hdr.pack(fill='x')

        tk.Label(hdr, text='⚡ Acciones de la reunión',
                 font=('Segoe UI', 13, 'bold'), fg='white', bg=_ACCENT).pack(side='left', padx=18)

        tk.Button(hdr, text='✉ Email', font=('Segoe UI', 9),
                  bg='white', fg=_ACCENT, relief='flat', padx=10,
                  command=self._send_email).pack(side='right', padx=6)
        tk.Button(hdr, text='🌐 Ver minutas', font=('Segoe UI', 9),
                  bg='white', fg=_ACCENT, relief='flat', padx=10,
                  command=self._open_html).pack(side='right', padx=2)

        # Status
        self._status_var = tk.StringVar(master=self.root, value='Cargando acciones...')
        tk.Label(self.root, textvariable=self._status_var,
                 font=('Segoe UI', 9), fg=_SUBTEXT, bg=_SURFACE,
                 anchor='w', pady=6).pack(fill='x', padx=18)

        # Canvas scrollable
        outer = tk.Frame(self.root, bg=_BG)
        outer.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        self._canvas = tk.Canvas(outer, bg=_BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient='vertical', command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self._cards_frame = tk.Frame(self._canvas, bg=_BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._cards_frame, anchor='nw')

        self._cards_frame.bind('<Configure>',
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox('all')))
        self._canvas.bind('<Configure>',
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        self._canvas.bind('<MouseWheel>',
            lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

    def _load_actions(self):
        from actions_enricher import load_enriched, enrich_and_save

        actions = load_enriched(self.minutes_path)
        if actions is not None:
            self._actions = actions
            self._render_cards()
        else:
            self._status_var.set('Analizando acciones con Claude...')

            def on_done():
                acts = load_enriched(self.minutes_path)
                self._actions = acts or []
                self.root.after(0, self._render_cards)

            enrich_and_save(self.minutes_path, CLAUDE_PROJECTS_DIR, on_done=on_done)

    def _render_cards(self):
        for w in self._cards_frame.winfo_children():
            w.destroy()

        if not self._actions:
            tk.Label(self._cards_frame, text='No se detectaron acciones en esta reunión.',
                     font=('Segoe UI', 11), fg=_SUBTEXT, bg=_BG,
                     wraplength=400).pack(pady=40)
            self._status_var.set('Sin acciones')
            return

        self._status_var.set(f'{len(self._actions)} acción(es) detectada(s)')

        for ad in self._actions:
            self._build_card(ad)

    def _build_card(self, ad: dict):
        executed = ad.get('executed', False)
        bg = _GREEN_BG if executed else _YELLOW_BG
        border = '#86efac' if executed else '#fbbf24'
        accent = '#16a34a' if executed else '#d97706'

        card = tk.Frame(self._cards_frame, bg=bg,
                        highlightbackground=border, highlightthickness=1,
                        pady=12, padx=14)
        card.pack(fill='x', pady=5, padx=4)

        # Tipo + título
        icon = TYPE_ICONS.get(ad.get('type', ''), '•')
        proj = ad.get('project', '')
        proj_label = f'  [{proj}]' if proj else ''

        hdr = tk.Frame(card, bg=bg)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"{icon} {ad['title'][:65]}{proj_label}",
                 font=('Segoe UI', 10, 'bold'), fg=_TEXT, bg=bg,
                 anchor='w', wraplength=440).pack(side='left', fill='x', expand=True)

        # Asignado
        if ad.get('assignee'):
            tk.Label(card, text=f"👤 {ad['assignee']}",
                     font=('Segoe UI', 8), fg=_SUBTEXT, bg=bg).pack(anchor='w', pady=(2, 0))

        # Prompt (expandible)
        prompt_var = tk.BooleanVar(master=self.root, value=False)
        prompt_frame = tk.Frame(card, bg=bg)

        prompt_box = ScrolledText(prompt_frame, height=5, bg='white', fg=_TEXT,
                                   font=('Segoe UI', 9), relief='flat', wrap='word',
                                   highlightbackground=_BORDER, highlightthickness=1)
        prompt_box.insert('1.0', ad.get('prompt_enriched') or ad.get('prompt_original', ''))
        prompt_box.pack(fill='x')
        prompt_box.bind('<FocusOut>', lambda e, idx=ad['index']: self._save_prompt(idx, prompt_box.get('1.0', 'end-1c')))

        def toggle_prompt(pf=prompt_frame, pv=prompt_var, btn=None):
            if pv.get():
                pf.pack_forget()
                pv.set(False)
                if btn: btn.configure(text='▼ Ver prompt')
            else:
                pf.pack(fill='x', pady=(6, 0))
                pv.set(True)
                if btn: btn.configure(text='▲ Ocultar prompt')

        toggle_btn = tk.Button(card, text='▼ Ver prompt',
                               font=('Segoe UI', 8), fg=_SUBTEXT, bg=bg, relief='flat',
                               cursor='hand2')
        toggle_btn.configure(command=lambda b=toggle_btn: toggle_prompt(btn=b))
        toggle_btn.pack(anchor='w', pady=(4, 0))

        # Botones
        btn_row = tk.Frame(card, bg=bg)
        btn_row.pack(fill='x', pady=(8, 0))

        exec_text = '↻ Re-ejecutar' if executed else '▶ Ejecutar en terminal'
        tk.Button(btn_row, text=exec_text,
                  font=('Segoe UI', 9, 'bold'),
                  bg=accent, fg='white', relief='flat', padx=12, pady=4,
                  cursor='hand2',
                  command=lambda ad=ad, pb=prompt_box: self._execute(ad, pb)).pack(side='left')

        if executed:
            tk.Label(btn_row, text='✓ Ejecutada', font=('Segoe UI', 8),
                     fg='#16a34a', bg=bg).pack(side='left', padx=10)

    def _save_prompt(self, action_index: int, prompt: str):
        from actions_enricher import update_action_prompt
        update_action_prompt(self.minutes_path, action_index, prompt)

    def _execute(self, ad: dict, prompt_box: ScrolledText):
        prompt = prompt_box.get('1.0', 'end-1c')
        proj = ad.get('project', '')
        proj_path = CLAUDE_PROJECTS_DIR / proj if proj else PROJECT_DIR

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_prompt = tmp_dir / 'prompt.txt'
        tmp_prompt.write_text(prompt, encoding='utf-8')

        ps1 = tmp_dir / 'run.ps1'
        ps1.write_text('\n'.join([
            '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8',
            f'Set-Location "{proj_path}"',
            f'Get-Content -Raw -Encoding UTF8 "{tmp_prompt}" | claude --verbose -p',
            "Read-Host 'Presiona Enter para cerrar'",
        ]), encoding='utf-8')

        try:
            subprocess.Popen([
                'wt', '--window', '0', 'new-tab',
                _PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ps1)
            ])
        except FileNotFoundError:
            subprocess.Popen([_PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ps1)])

        from actions_enricher import update_action_executed
        update_action_executed(self.minutes_path, ad['index'], prompt)
        self._status_var.set(f"Ejecutando: {ad['title'][:50]}...")

    def _open_html(self):
        import os
        html_path = self.minutes_path.with_suffix('.html')
        if html_path.exists():
            os.startfile(str(html_path))
        else:
            from html_exporter import export_to_html
            export_to_html(self.minutes_path, self.minutes_path.stem)

    def _send_email(self):
        from outlook_sender import send_minutes_email
        html_path = self.minutes_path.with_suffix('.html')
        if not html_path.exists():
            from html_exporter import export_to_html
            export_to_html(self.minutes_path, self.minutes_path.stem, open_browser=False)

        send_minutes_email(
            minutes_path=self.minutes_path,
            html_path=html_path,
            title=self.minutes_path.stem,
            participants=[],
        )

    def run(self):
        self.root.mainloop()


def open_actions_window(minutes_path: Path):
    def _run():
        win = ActionsWindow(minutes_path)
        win.run()
    t = threading.Thread(target=_run, daemon=True, name='ActionsWindow')
    t.start()
