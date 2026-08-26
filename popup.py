import threading
import tkinter as tk

from config import POPUP_TIMEOUT, get_ui_language
from tk_thread import get_root, run_in_tk

_STR = {
    'es': dict(title='Reunion de Teams detectada', subtitle='Quieres grabar el audio?',
               yes='  Grabar  ', no='No grabar'),
    'en': dict(title='Teams meeting detected', subtitle='Do you want to record the audio?',
               yes='  Record  ', no="Don't record"),
}

BG_DARK  = '#1e1e2e'
FG_TITLE = '#cdd6f4'
FG_SUB   = '#a6adc8'
FG_MUTED = '#6c7086'
BTN_YES  = '#89b4fa'
BTN_NO   = '#45475a'
BORDER   = '#585b70'


class RecordingPopup:
    def __init__(self, on_yes=None, on_no=None, timeout=POPUP_TIMEOUT):
        self._on_yes = on_yes
        self._on_no  = on_no
        self._timeout = timeout
        self._answered = False
        self._top: tk.Toplevel | None = None
        self._countdown_var: tk.StringVar | None = None
        self._remaining = timeout

    def show(self):
        run_in_tk(self._create)

    def _create(self):
        s = _STR.get(get_ui_language(), _STR['en'])
        root = get_root()

        top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes('-topmost', True)
        top.attributes('-alpha', 0.96)
        top.lift()

        W, H = 340, 118
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        top.geometry(f"{W}x{H}+{sw - W - 20}+{sh - H - 64}")
        top.configure(bg=BORDER)

        frame = tk.Frame(top, bg=BG_DARK, padx=14, pady=10)
        frame.pack(fill='both', expand=True, padx=1, pady=1)

        tk.Label(frame, text=s['title'],
                 font=('Segoe UI', 11, 'bold'), fg=FG_TITLE, bg=BG_DARK).pack(anchor='w')
        tk.Label(frame, text=s['subtitle'],
                 font=('Segoe UI', 9), fg=FG_SUB, bg=BG_DARK).pack(anchor='w')

        btn_frame = tk.Frame(frame, bg=BG_DARK)
        btn_frame.pack(fill='x', pady=(14, 0))

        tk.Button(btn_frame, text=s['yes'], font=('Segoe UI', 9, 'bold'),
                  bg=BTN_YES, fg=BG_DARK, relief='flat', cursor='hand2',
                  command=self._yes).pack(side='left', padx=(0, 8))

        tk.Button(btn_frame, text=s['no'], font=('Segoe UI', 9),
                  bg=BTN_NO, fg=FG_TITLE, relief='flat', cursor='hand2',
                  command=self._no).pack(side='left')

        self._countdown_var = tk.StringVar(master=root, value=f"({self._timeout}s)")
        tk.Label(btn_frame, textvariable=self._countdown_var,
                 font=('Segoe UI', 8), fg=FG_MUTED, bg=BG_DARK).pack(side='right')

        top.protocol('WM_DELETE_WINDOW', self._no)
        self._top = top
        self._remaining = self._timeout
        top.after(1000, self._tick)

    def _tick(self):
        if self._answered or self._top is None:
            return
        self._remaining -= 1
        if self._countdown_var:
            self._countdown_var.set(f"({self._remaining}s)")
        if self._remaining <= 0:
            self._no()
        else:
            self._top.after(1000, self._tick)

    def _yes(self):
        if self._answered:
            return
        self._answered = True
        self._close()
        if self._on_yes:
            threading.Thread(target=self._on_yes, daemon=True, name='PopupYes').start()

    def _no(self):
        if self._answered:
            return
        self._answered = True
        self._close()
        if self._on_no:
            threading.Thread(target=self._on_no, daemon=True, name='PopupNo').start()

    def _close(self):
        run_in_tk(self._close_in_tk)

    def _close_in_tk(self):
        try:
            if self._top:
                self._top.destroy()
                self._top = None
        except Exception:
            pass
