import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from config import PROJECT_DIR
from storage import list_recordings, MINUTES_DIR

log = logging.getLogger(__name__)

_CLAUDE_EXE = r'C:\Users\ines.campos\.local\bin\claude.exe'
_CLAUDE_BIN = _CLAUDE_EXE if Path(_CLAUDE_EXE).exists() else shutil.which('claude')

CLAUDE_PROJECTS_DIR = PROJECT_DIR.parent

# PowerShell 7
_PWSH = next(
    (p for p in [
        r'C:\Program Files\PowerShell\7\pwsh.exe',
        r'C:\Program Files\PowerShell\7.4\pwsh.exe',
        shutil.which('pwsh'),
    ] if p and Path(p).exists()),
    'powershell'
)

# Paleta Catppuccin Mocha
_BG      = '#1e1e2e'
_SURFACE = '#313244'
_SURF2   = '#181825'
_BORDER  = '#45475a'
_TEXT    = '#cdd6f4'
_SUBTEXT = '#a6adc8'
_ACCENT  = '#89b4fa'
_GREEN   = '#a6e3a1'
_RED     = '#f38ba8'
_YELLOW  = '#f9e2af'

TYPE_BADGES = {
    'instruction':    '⚡',
    'code_change':    '💻',
    'document_change':'📄',
}


def _md_to_html(md_text: str) -> str:
    try:
        import markdown
        body = markdown.markdown(md_text, extensions=['fenced_code', 'tables'])
    except Exception:
        body = f'<pre>{md_text}</pre>'
    return f"""<html><body style="background:{_BG};color:{_TEXT};font-family:Segoe UI,sans-serif;
font-size:13px;padding:16px;line-height:1.6">
<style>code{{background:{_SURFACE};padding:2px 6px;border-radius:3px}}
pre{{background:{_SURFACE};padding:12px;border-radius:6px;overflow-x:auto}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid {_BORDER};padding:6px 10px}}
th{{background:{_SURFACE}}}
blockquote{{border-left:3px solid {_ACCENT};margin:0;padding-left:12px;color:{_SUBTEXT}}}
</style>{body}</body></html>"""


class ActionsWindow:
    def __init__(self, initial_tab='split'):
        self.root = tk.Tk()
        self.root.title('TeamsRecorder — Minutas y Acciones')
        self.root.configure(bg=_BG)
        self.root.geometry('1200x800')

        self._minutes_list: list[Path] = sorted(MINUTES_DIR.glob('*.md'),
                                                  key=lambda p: p.stat().st_mtime, reverse=True)
        self._current_minutes: Path | None = self._minutes_list[0] if self._minutes_list else None
        self._actions: list[dict] = []
        self._enriching_for: Path | None = None
        self._card_frames: list[tk.Frame] = []

        self._build_ui()
        if self._current_minutes:
            self._load_minutes(self._current_minutes)
        self._switch_tab(initial_tab)

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=_SURF2, pady=6)
        hdr.pack(fill='x', padx=0)

        tk.Label(hdr, text='Minutas:', bg=_SURF2, fg=_SUBTEXT,
                 font=('Segoe UI', 9)).pack(side='left', padx=(12, 4))

        self._minutes_var = tk.StringVar(master=self.root)
        names = [p.stem for p in self._minutes_list] or ['(ninguna)']
        self._minutes_cb = ttk.Combobox(hdr, textvariable=self._minutes_var,
                                         values=names, state='readonly', width=50)
        self._minutes_cb.pack(side='left', padx=4)
        if names[0] != '(ninguna)':
            self._minutes_cb.current(0)
        self._minutes_cb.bind('<<ComboboxSelected>>', self._on_minutes_select)

        tk.Button(hdr, text='Copiar minutas', bg=_SURFACE, fg=_TEXT, relief='flat',
                  command=self._copy_minutes).pack(side='left', padx=8)
        tk.Button(hdr, text='Email', bg=_SURFACE, fg=_TEXT, relief='flat',
                  command=self._send_email).pack(side='left')

        # Tabs
        tab_bar = tk.Frame(self.root, bg=_SURF2)
        tab_bar.pack(fill='x')
        self._tab_btns = {}
        for tab, label in [('minutes', '📄 Minutas'), ('actions', '⚡ Acciones'), ('split', '▣ Dividido')]:
            b = tk.Button(tab_bar, text=label, bg=_SURF2, fg=_SUBTEXT, relief='flat',
                          font=('Segoe UI', 9), padx=12,
                          command=lambda t=tab: self._switch_tab(t))
            b.pack(side='left')
            self._tab_btns[tab] = b

        # PanedWindow
        self._paned = tk.PanedWindow(self.root, orient='horizontal', bg=_BORDER,
                                      sashwidth=4, sashrelief='flat')
        self._paned.pack(fill='both', expand=True)

        # Panel izquierdo — minutas
        self._left = tk.Frame(self._paned, bg=_BG)
        self._paned.add(self._left, minsize=300)

        try:
            from tkinterweb import HtmlFrame
            self._html_view = HtmlFrame(self._left, messages_enabled=False)
            self._html_view.pack(fill='both', expand=True)
            self._use_html = True
        except Exception:
            self._text_view = ScrolledText(self._left, bg=_BG, fg=_TEXT, wrap='word',
                                            font=('Segoe UI', 10), relief='flat')
            self._text_view.pack(fill='both', expand=True)
            self._use_html = False

        # Sección re-generar
        regen = tk.Frame(self._left, bg=_SURF2, pady=8)
        regen.pack(fill='x', side='bottom')
        tk.Label(regen, text='Contexto adicional (opcional):',
                 bg=_SURF2, fg=_SUBTEXT, font=('Segoe UI', 8)).pack(anchor='w', padx=8)
        self._ctx_text = ScrolledText(regen, height=3, bg=_SURFACE, fg=_SUBTEXT,
                                       font=('Segoe UI', 9), relief='flat')
        self._ctx_text.insert('1.0', 'Escribe contexto adicional aquí...')
        self._ctx_text.bind('<FocusIn>', lambda e: self._ctx_text.delete('1.0', 'end')
                             if self._ctx_text.get('1.0', 'end-1c') == 'Escribe contexto adicional aquí...' else None)
        self._ctx_text.pack(fill='x', padx=8, pady=4)

        btn_row = tk.Frame(regen, bg=_SURF2)
        btn_row.pack(fill='x', padx=8)
        tk.Button(btn_row, text='⟳ Re-generar minutas', bg=_ACCENT, fg=_BG,
                  relief='flat', font=('Segoe UI', 9, 'bold'),
                  command=self._do_regen).pack(side='left')
        self._regen_status = tk.StringVar(master=self.root)
        tk.Label(btn_row, textvariable=self._regen_status,
                 bg=_SURF2, fg=_YELLOW, font=('Segoe UI', 8)).pack(side='left', padx=8)

        self._transcript_label = tk.StringVar(master=self.root, value='')
        tk.Label(regen, textvariable=self._transcript_label,
                 bg=_SURF2, fg=_SUBTEXT, font=('Segoe UI', 8)).pack(anchor='w', padx=8)

        # Panel derecho — acciones
        self._right = tk.Frame(self._paned, bg=_BG)
        self._paned.add(self._right, minsize=300)

        self._batch_bar = tk.Frame(self._right, bg=_SURF2)
        self._batch_bar.pack(fill='x')

        canvas_frame = tk.Frame(self._right, bg=_BG)
        canvas_frame.pack(fill='both', expand=True)

        self._canvas = tk.Canvas(canvas_frame, bg=_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self._cards_frame = tk.Frame(self._canvas, bg=_BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._cards_frame, anchor='nw')

        self._cards_frame.bind('<Configure>', self._on_cards_resize)
        self._canvas.bind('<Configure>', self._on_canvas_resize)
        self._canvas.bind('<MouseWheel>', self._on_mousewheel)

        # Status bar
        self._status = tk.StringVar(master=self.root, value='Listo')
        tk.Label(self.root, textvariable=self._status, bg=_SURF2, fg=_SUBTEXT,
                 font=('Segoe UI', 8), anchor='w').pack(fill='x', side='bottom')

    def _on_cards_resize(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        widget = event.widget
        if isinstance(widget, tk.Text):
            return
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _switch_tab(self, tab: str):
        for name, btn in self._tab_btns.items():
            btn.configure(fg=_TEXT if name == tab else _SUBTEXT,
                          bg=_SURFACE if name == tab else _SURF2)
        if tab == 'minutes':
            self._paned.forget(self._right) if self._right.winfo_manager() else None
            if not self._left.winfo_manager():
                self._paned.add(self._left)
        elif tab == 'actions':
            self._paned.forget(self._left) if self._left.winfo_manager() else None
            if not self._right.winfo_manager():
                self._paned.add(self._right)
        else:  # split
            if not self._left.winfo_manager():
                self._paned.add(self._left)
            if not self._right.winfo_manager():
                self._paned.add(self._right)

    def _on_minutes_select(self, event=None):
        idx = self._minutes_cb.current()
        if 0 <= idx < len(self._minutes_list):
            self._load_minutes(self._minutes_list[idx])

    def _load_minutes(self, path: Path):
        self._current_minutes = path
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            return

        if self._use_html:
            self._html_view.load_html(_md_to_html(text))
        else:
            self._text_view.configure(state='normal')
            self._text_view.delete('1.0', 'end')
            self._text_view.insert('1.0', text)
            self._text_view.configure(state='disabled')

        # Transcript asociado
        tr = self._find_transcript(path)
        self._transcript_label.set(f"Transcript: {tr.name}" if tr else "⚠ Transcript no encontrado")

        # Cargar acciones
        from actions_enricher import load_enriched
        actions = load_enriched(path)
        if actions is not None:
            self._actions = actions
            self._rebuild_cards()
        else:
            self._actions = []
            self._rebuild_cards()
            self._start_live_enrichment(path)

        self._status.set(f"Cargado: {path.name}")

    def _find_transcript(self, minutes_path: Path) -> Path | None:
        from config import RECORDINGS_DIR
        stem = minutes_path.stem
        m_ts = stem[:13]  # YYYYMMDD_HHMM
        if len(m_ts) >= 13:
            y, mo, d = m_ts[:4], m_ts[4:6], m_ts[6:8]
            hh, mm = m_ts[9:11], m_ts[11:13]
            prefix = f"{y}-{mo}-{d}_{hh}-{mm}"
            for folder in (RECORDINGS_DIR, RECORDINGS_DIR / 'processed'):
                for f in folder.glob(f"{prefix}*_transcript.txt"):
                    return f
        return None

    def _start_live_enrichment(self, path: Path):
        if self._enriching_for == path:
            return
        self._enriching_for = path
        self._status.set('Analizando acciones...')

        from actions_enricher import enrich_and_save

        def on_done():
            if self._current_minutes == path:
                from actions_enricher import load_enriched
                actions = load_enriched(path)
                if actions:
                    self._actions = actions
                    self.root.after(0, self._rebuild_cards)
                self._status.set('Acciones listas')
            self._enriching_for = None

        enrich_and_save(path, CLAUDE_PROJECTS_DIR, on_done=on_done)

    def _rebuild_cards(self):
        for w in self._card_frames:
            w.destroy()
        self._card_frames.clear()

        for w in self._batch_bar.winfo_children():
            w.destroy()

        if not self._actions:
            tk.Label(self._cards_frame, text='Sin acciones detectadas.',
                     bg=_BG, fg=_SUBTEXT, font=('Segoe UI', 10)).pack(pady=20)
            return

        # Agrupar por proyecto
        by_project: dict[str, list[dict]] = {}
        for a in self._actions:
            proj = a.get('project') or '(sin proyecto)'
            by_project.setdefault(proj, []).append(a)

        # Banner batch
        for proj, acts in by_project.items():
            if proj == '(sin proyecto)':
                continue
            proj_path = CLAUDE_PROJECTS_DIR / proj
            row = tk.Frame(self._batch_bar, bg=_SURF2)
            row.pack(side='left', padx=6, pady=4)
            tk.Label(row, text=proj, bg=_SURF2, fg=_ACCENT,
                     font=('Segoe UI', 8, 'bold')).pack(side='left', padx=4)
            tk.Button(row, text=f'▶ Secuencia ({len(acts)})',
                      bg=_GREEN, fg=_BG, relief='flat', font=('Segoe UI', 8),
                      command=lambda a=acts, p=proj_path: self._execute_in_terminal(
                          [(x['prompt_enriched'], x['index']) for x in a], p)
                      ).pack(side='left', padx=2)
            tk.Button(row, text=f'▒▒ Paralelo ({len(acts)})',
                      bg=_SURFACE, fg=_TEXT, relief='flat', font=('Segoe UI', 8),
                      command=lambda a=acts, p=proj_path: self._execute_parallel(
                          [(x['prompt_enriched'], x['index']) for x in a], p)
                      ).pack(side='left', padx=2)

        # Tarjetas
        for ad in self._actions:
            card = self._build_card(ad)
            card.pack(fill='x', padx=8, pady=4)
            self._card_frames.append(card)

    def _build_card(self, ad: dict) -> tk.Frame:
        executed = ad.get('executed', False)
        bg = '#1a2a1a' if executed else _SURFACE
        card = tk.Frame(self._cards_frame, bg=bg, pady=8, padx=10,
                        highlightbackground=_BORDER, highlightthickness=1)

        collapsed = tk.BooleanVar(master=self.root, value=executed)

        # Header
        hdr = tk.Frame(card, bg=bg)
        hdr.pack(fill='x')

        badge = TYPE_BADGES.get(ad.get('type', ''), '•')
        tk.Label(hdr, text=f"{badge} #{ad['index']+1}  {ad['title'][:70]}",
                 bg=bg, fg=_TEXT, font=('Segoe UI', 9, 'bold'), anchor='w').pack(side='left', fill='x', expand=True)

        expand_btn = tk.Button(hdr, text='Mostrar' if executed else '▼',
                               bg=bg, fg=_SUBTEXT, relief='flat', font=('Segoe UI', 8))
        expand_btn.pack(side='right')

        dup_btn = tk.Button(hdr, text='⊩ Duplicar', bg=bg, fg=_SUBTEXT,
                            relief='flat', font=('Segoe UI', 8),
                            command=lambda: self._duplicate_action(ad))
        dup_btn.pack(side='right', padx=4)

        body = tk.Frame(card, bg=bg)

        def toggle():
            if collapsed.get():
                body.pack(fill='x', pady=(6, 0))
                collapsed.set(False)
                expand_btn.configure(text='▲')
            else:
                body.pack_forget()
                collapsed.set(True)
                expand_btn.configure(text='Mostrar')

        expand_btn.configure(command=toggle)

        # Tarea propuesta
        tk.Label(body, text='TAREA PROPUESTA', bg=bg, fg=_SUBTEXT,
                 font=('Segoe UI', 7, 'bold')).pack(anchor='w')
        orig_lines = min(max(len(ad['prompt_original'].splitlines()), 3), 8)
        orig_box = tk.Text(body, height=orig_lines, bg=_SURF2, fg=_SUBTEXT,
                           font=('Segoe UI', 9), relief='flat', wrap='word', state='normal')
        orig_box.insert('1.0', ad.get('prompt_original', ''))
        orig_box.configure(state='disabled')
        orig_box.pack(fill='x', pady=(0, 6))
        orig_box.bind('<MouseWheel>', lambda e: 'break')

        # Proyecto
        proj_row = tk.Frame(body, bg=bg)
        proj_row.pack(fill='x', pady=(0, 4))
        tk.Label(proj_row, text='PROYECTO:', bg=bg, fg=_SUBTEXT,
                 font=('Segoe UI', 7, 'bold')).pack(side='left')

        proj_var = tk.StringVar(master=self.root, value=ad.get('project') or '')
        projects = [d.name for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()] if CLAUDE_PROJECTS_DIR.exists() else []
        proj_cb = ttk.Combobox(proj_row, textvariable=proj_var, values=projects, width=30)
        if ad.get('project') and ad['project'] in projects:
            proj_cb.current(projects.index(ad['project']))
        proj_cb.config(state='readonly')
        proj_cb.pack(side='left', padx=6)

        assignee = ad.get('assignee')
        if assignee:
            tk.Label(proj_row, text=f'👤 {assignee}', bg=bg, fg=_YELLOW,
                     font=('Segoe UI', 8)).pack(side='left', padx=4)
        elif not ad.get('project'):
            tk.Label(proj_row, text='⚠ Quizas no te aplique', bg=bg, fg=_YELLOW,
                     font=('Segoe UI', 8)).pack(side='left', padx=4)

        # Prompt propuesto
        tk.Label(body, text='PROMPT PROPUESTO', bg=bg, fg=_SUBTEXT,
                 font=('Segoe UI', 7, 'bold')).pack(anchor='w')

        prompt_expanded = tk.BooleanVar(master=self.root, value=False)
        prompt_box = ScrolledText(body, height=8, bg=_SURF2, fg=_TEXT,
                                   font=('Segoe UI', 9), relief='flat', wrap='word')
        prompt_box.insert('1.0', ad.get('prompt_enriched') or ad.get('prompt_original', ''))
        prompt_box.pack(fill='x')

        def save_prompt_edit(event=None):
            new_prompt = prompt_box.get('1.0', 'end-1c')
            from actions_enricher import update_action_prompt
            if self._current_minutes:
                update_action_prompt(self._current_minutes, ad['index'], new_prompt)

        prompt_box.bind('<FocusOut>', save_prompt_edit)

        def toggle_expand():
            if prompt_expanded.get():
                prompt_box.configure(height=8)
                prompt_expanded.set(False)
                exp_btn.configure(text='⊕')
            else:
                prompt_box.configure(height=22)
                prompt_expanded.set(True)
                exp_btn.configure(text='⊖')

        exp_btn = tk.Button(body, text='⊕', bg=bg, fg=_SUBTEXT, relief='flat',
                            font=('Segoe UI', 8), command=toggle_expand)
        exp_btn.pack(anchor='e')

        # Botones ejecutar
        btn_row = tk.Frame(body, bg=bg)
        btn_row.pack(fill='x', pady=(6, 0))

        exec_text = '↻ Re-ejecutar' if executed else '▶ Ejecutar'
        exec_bg   = _SURFACE if executed else _GREEN
        exec_fg   = _SUBTEXT if executed else _BG

        def execute():
            prompt = prompt_box.get('1.0', 'end-1c')
            proj = proj_var.get()
            proj_path = CLAUDE_PROJECTS_DIR / proj if proj else PROJECT_DIR
            self._execute_in_terminal([(prompt, ad['index'])], proj_path)

        tk.Button(btn_row, text=exec_text, bg=exec_bg, fg=exec_fg,
                  relief='flat', font=('Segoe UI', 9, 'bold'),
                  command=execute).pack(side='left', padx=(0, 6))

        if not executed:
            body.pack(fill='x', pady=(6, 0))

        return card

    def _duplicate_action(self, ad: dict):
        self._actions.append({**ad, 'index': len(self._actions), 'executed': False})
        self._rebuild_cards()

    def _execute_in_terminal(self, tasks: list[tuple[str, int]], proj_path: Path):
        tmp_dir = Path(tempfile.mkdtemp())
        ps1_lines = [
            '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8',
            '$env:PYTHONUTF8 = "1"',
        ]
        for key in ('CLAUDE_SESSION_ID', 'CLAUDE_API_KEY', 'ANTHROPIC_API_KEY', 'MCP_SERVERS'):
            ps1_lines.append(f'[System.Environment]::SetEnvironmentVariable("{key}", $null, "Process")')

        ps1_lines.append(f'Set-Location "{proj_path}"')

        for i, (prompt, action_idx) in enumerate(tasks):
            tmp_prompt = tmp_dir / f'prompt_{i}.txt'
            tmp_prompt.write_text(prompt, encoding='utf-8')
            ps1_lines += [
                f'Write-Host "─── Tarea {i+1}/{len(tasks)} ───" -ForegroundColor Cyan',
                f'$out = Get-Content -Raw -Encoding UTF8 "{tmp_prompt}" | claude --verbose -p 2>&1 | Tee-Object -Variable result',
                '$session = ($result | Select-String -Pattern "[0-9a-f]{8}-[0-9a-f-]{{35}}").Matches.Value | Select-Object -First 1',
                'if ($session) { Write-Host "Retomar sesion: claude --resume $session" -ForegroundColor Yellow }',
            ]

        if len(tasks) > 1:
            ps1_lines.append('Write-Host "✓ Todas las tareas completadas." -ForegroundColor Green')
        ps1_lines.append("Read-Host 'Presiona Enter para cerrar'")

        ps1_path = tmp_dir / 'run_tasks.ps1'
        ps1_path.write_text('\n'.join(ps1_lines), encoding='utf-8')

        try:
            subprocess.Popen([
                'wt', '--window', '0', 'new-tab',
                _PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ps1_path)
            ])
        except FileNotFoundError:
            subprocess.Popen([
                _PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ps1_path)
            ])

        from actions_enricher import update_action_executed
        for prompt, action_idx in tasks:
            if self._current_minutes:
                update_action_executed(self._current_minutes, action_idx, prompt)

    def _execute_parallel(self, tasks: list[tuple[str, int]], proj_path: Path):
        for task in tasks:
            self._execute_in_terminal([task], proj_path)

    def _copy_minutes(self):
        if not self._current_minutes:
            return
        try:
            text = self._current_minutes.read_text(encoding='utf-8')
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._status.set('Minutas copiadas al portapapeles')
        except Exception as e:
            self._status.set(f'Error: {e}')

    def _send_email(self):
        if not self._current_minutes:
            return
        try:
            import win32com.client
            text = self._current_minutes.read_text(encoding='utf-8')
            outlook = win32com.client.Dispatch('Outlook.Application')
            mail = outlook.CreateItem(0)
            mail.Subject = f"Minutas: {self._current_minutes.stem}"
            mail.Body = text
            mail.Display()
        except Exception:
            self._copy_minutes()
            self._status.set('Outlook no disponible — minutas copiadas al portapapeles')

    def _do_regen(self):
        if not self._current_minutes:
            return
        tr = self._find_transcript(self._current_minutes)
        if not tr:
            self._regen_status.set('⚠ No se encontró el transcript')
            return

        extra = self._ctx_text.get('1.0', 'end-1c').strip()
        if extra == 'Escribe contexto adicional aquí...':
            extra = None

        self._regen_status.set('⏳ Llamando a claude -p...')

        from minutes_generator import generate_minutes, extract_title_from_minutes, save_minutes
        from actions_enricher import enrich_and_save, get_actions_path
        from storage import get_minutes_path

        transcript_text = tr.read_text(encoding='utf-8')
        fake_rec = tr.parent / tr.name.replace('_transcript.txt', '.wav')
        minutes_path = self._current_minutes

        def on_done(raw):
            if not raw:
                self.root.after(0, lambda: self._regen_status.set('✗ Error generando minutas'))
                return
            title, content = extract_title_from_minutes(raw)
            save_minutes(content, minutes_path)
            ap = get_actions_path(minutes_path)
            if ap.exists():
                ap.unlink()
            self.root.after(0, lambda: self._regen_status.set('⏳ Analizando acciones...'))

            def on_enriched():
                self.root.after(0, self._reload_after_regen)

            enrich_and_save(minutes_path, CLAUDE_PROJECTS_DIR, on_done=on_enriched)

        generate_minutes(transcript_text, fake_rec, extra_context=extra, on_complete=on_done)

    def _reload_after_regen(self):
        self._regen_status.set('✓ Minutas y acciones actualizadas')
        self._load_minutes(self._current_minutes)

    def run(self):
        self.root.mainloop()


def open_actions_window(initial_tab: str = 'split'):
    def _run():
        win = ActionsWindow(initial_tab=initial_tab)
        win.run()
    t = threading.Thread(target=_run, daemon=True, name='ActionsUI')
    t.start()
