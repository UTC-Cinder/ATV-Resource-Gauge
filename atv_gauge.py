import tkinter as tk
import ctypes
import csv
import os
from datetime import datetime

# Fix blank window on high-DPI screens
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── ATV Color Palette ──
BG      = "#08090c"
SURFACE = "#171c26"
BORDER  = "#222a38"
TEAL    = "#4cb8c4"
GOLD    = "#c9a84c"
ROSE    = "#cf6679"
DIM     = "#3a4a5a"
MUTED   = "#7a8fa0"
LIGHT   = "#b8ccd8"
WHITE   = "#f4f8fc"
GREEN   = "#4cc47a"

# ── Estimation constants ──
CHARS_PER_TOKEN   = 4.0
KWH_PER_1K_TOKENS = 0.003
WATER_ML_PER_KWH  = 2.0
RESPONSE_RATIO    = 2.5

TEAL_MAX = 500
GOLD_MAX = 2000

def estimate(text):
    chars = len(text)
    pt = chars / CHARS_PER_TOKEN
    rt = pt * RESPONSE_RATIO
    tt = pt + rt
    p_kwh = (pt / 1000) * KWH_PER_1K_TOKENS
    t_kwh = (tt / 1000) * KWH_PER_1K_TOKENS
    p_h2o = p_kwh * WATER_ML_PER_KWH * 1000
    t_h2o = t_kwh * WATER_ML_PER_KWH * 1000
    return {
        "prompt_tokens":   round(pt),
        "response_tokens": round(rt),
        "total_tokens":    round(tt),
        "prompt_kwh":      p_kwh,
        "total_kwh":       t_kwh,
        "prompt_water":    p_h2o,
        "total_water":     t_h2o,
    }

def indicator_color(total_tokens):
    if total_tokens <= TEAL_MAX:
        return TEAL
    elif total_tokens <= GOLD_MAX:
        return GOLD
    return ROSE

def fmt_kwh(kwh):
    if kwh < 0.000001:
        return "< 0.001 mWh"
    elif kwh < 0.001:
        return f"{kwh*1000*1000:.1f} uWh"
    elif kwh < 1:
        return f"{kwh*1000:.3f} mWh"
    return f"{kwh:.5f} kWh"

def fmt_water(ml):
    if ml < 0.01:
        return f"{ml*1000:.2f} uL"
    elif ml < 1000:
        return f"{ml:.3f} mL"
    return f"{ml/1000:.4f} L"

class ATVGauge(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ATV Resource Gauge")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        # Session tracking
        self.session_start  = datetime.now()
        self.session_log    = []
        self.session_tokens = 0
        self.session_kwh    = 0.0
        self.session_water  = 0.0
        self.prompt_count   = 0
        self.last_estimate  = None

        self._build()
        self._refresh("")

        # Auto-size and position top-right
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        x = sw - w - 20
        y = 20
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(hdr, text="AGAINST  THE  VOID", bg=BG, fg=TEAL,
                 font=("Courier New", 8, "bold"), anchor="w").pack(side="left")
        tk.Label(hdr, text="RESOURCE GAUGE", bg=BG, fg=DIM,
                 font=("Courier New", 7), anchor="e").pack(side="right")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        # Indicator row
        ind = tk.Frame(self, bg=BG)
        ind.pack(fill="x", padx=16, pady=(0, 10))
        self.dot_c = tk.Canvas(ind, width=14, height=14, bg=BG, highlightthickness=0)
        self.dot_c.pack(side="left", padx=(0, 8))
        self.dot = self.dot_c.create_oval(2, 2, 12, 12, fill=DIM, outline="")
        self.lbl_main = tk.Label(ind, text="paste a prompt to begin",
                                  bg=BG, fg=MUTED,
                                  font=("Courier New", 9, "bold"), anchor="w")
        self.lbl_main.pack(side="left")

        # Readout panel
        panel = tk.Frame(self, bg=SURFACE)
        panel.pack(fill="x", padx=16, pady=(0, 8))

        def section(title):
            tk.Frame(panel, bg=BORDER, height=1).pack(fill="x")
            tk.Label(panel, text=f"  {title}", bg=SURFACE, fg=DIM,
                     font=("Courier New", 7)).pack(fill="x", padx=10, pady=(5, 0))

        def row(label, var, fg=LIGHT):
            f = tk.Frame(panel, bg=SURFACE)
            f.pack(fill="x", padx=10, pady=3)
            tk.Label(f, text=label, bg=SURFACE, fg=MUTED,
                     font=("Courier New", 8), anchor="w").pack(side="left")
            tk.Label(f, textvariable=var, bg=SURFACE, fg=fg,
                     font=("Courier New", 9, "bold"), anchor="e").pack(side="right")

        self.v_pt  = tk.StringVar(value="--")
        self.v_rt  = tk.StringVar(value="--")
        self.v_tt  = tk.StringVar(value="--")
        self.v_ppw = tk.StringVar(value="--")
        self.v_tpw = tk.StringVar(value="--")
        self.v_ph  = tk.StringVar(value="--")
        self.v_th  = tk.StringVar(value="--")

        section("TOKENS")
        row("your prompt",   self.v_pt,  LIGHT)
        row("est. response", self.v_rt,  MUTED)
        row("round trip",    self.v_tt,  WHITE)

        section("POWER")
        row("your prompt",   self.v_ppw, LIGHT)
        row("round trip",    self.v_tpw, WHITE)

        section("WATER")
        row("your prompt",   self.v_ph,  LIGHT)
        row("round trip",    self.v_th,  WHITE)

        tk.Frame(panel, bg=BORDER, height=1).pack(fill="x", pady=(6, 0))

        # Session totals panel
        stot = tk.Frame(self, bg=SURFACE)
        stot.pack(fill="x", padx=16, pady=(0, 8))

        tk.Frame(stot, bg=TEAL, height=1).pack(fill="x")
        tk.Label(stot, text="  SESSION TOTALS", bg=SURFACE, fg=TEAL,
                 font=("Courier New", 7)).pack(fill="x", padx=10, pady=(5, 0))

        def srow(label, var, fg=TEAL):
            f = tk.Frame(stot, bg=SURFACE)
            f.pack(fill="x", padx=10, pady=2)
            tk.Label(f, text=label, bg=SURFACE, fg=MUTED,
                     font=("Courier New", 8), anchor="w").pack(side="left")
            tk.Label(f, textvariable=var, bg=SURFACE, fg=fg,
                     font=("Courier New", 9, "bold"), anchor="e").pack(side="right")

        self.v_st  = tk.StringVar(value="0")
        self.v_sc  = tk.StringVar(value="0 prompts")
        self.v_spw = tk.StringVar(value="--")
        self.v_sh  = tk.StringVar(value="--")

        srow("total tokens",   self.v_st,  TEAL)
        srow("prompts logged", self.v_sc,  MUTED)
        srow("total power",    self.v_spw, TEAL)
        srow("total water",    self.v_sh,  TEAL)

        tk.Frame(stot, bg=BORDER, height=1).pack(fill="x", pady=(4, 0))

        # Input label
        tk.Label(self, text="PASTE PROMPT BELOW", bg=BG, fg=MUTED,
                 font=("Courier New", 7)).pack(anchor="w", padx=16, pady=(6, 3))

        # Text box
        border_frame = tk.Frame(self, bg=TEAL, padx=1, pady=1)
        border_frame.pack(fill="x", padx=16)

        self.txt = tk.Text(
            border_frame,
            height=5,
            bg="#1a2030",
            fg=WHITE,
            insertbackground=TEAL,
            font=("Courier New", 9),
            relief="flat",
            bd=6,
            wrap="word"
        )
        self.txt.pack(fill="x")
        self.txt.bind("<KeyRelease>", lambda e: self._on_change())
        self.txt.bind("<<Paste>>", lambda e: self.after(10, self._on_change))

        # Button row
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(8, 6))

        clear_btn = tk.Button(btn_row, text="LOG + CLEAR", bg=BORDER, fg=LIGHT,
                  font=("Courier New", 8, "bold"), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=DIM, activeforeground=WHITE)
        clear_btn.configure(command=lambda: self._log_and_clear())
        clear_btn.pack(side="left")

        export_btn = tk.Button(btn_row, text="EXPORT CSV", bg=TEAL, fg=BG,
                  font=("Courier New", 8, "bold"), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=GOLD, activeforeground=BG)
        export_btn.configure(command=lambda: self._export_csv())
        export_btn.pack(side="left", padx=(8, 0))

        self.lbl_status = tk.Label(btn_row, text="", bg=BG, fg=GREEN,
                                    font=("Courier New", 7), anchor="e")
        self.lbl_status.pack(side="right")

        # Footer
        tk.Label(self, text="~4 chars/token  |  Sonnet estimate  |  Against the Void",
                 bg=BG, fg=DIM, font=("Courier New", 7)).pack(pady=(2, 12))

    def _on_change(self):
        self._refresh(self.txt.get("1.0", "end-1c"))

    def _log_and_clear(self):
        if self.last_estimate:
            e = self.last_estimate
            self.prompt_count   += 1
            self.session_tokens += e["total_tokens"]
            self.session_kwh    += e["total_kwh"]
            self.session_water  += e["total_water"]

            self.session_log.append({
                "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "prompt_num":      self.prompt_count,
                "prompt_tokens":   e["prompt_tokens"],
                "response_tokens": e["response_tokens"],
                "total_tokens":    e["total_tokens"],
                "total_kwh":       round(e["total_kwh"], 8),
                "total_water_ml":  round(e["total_water"], 4),
            })

            self._update_session_totals()
            self.lbl_status.config(text=f"prompt {self.prompt_count} logged")
            self.after(2000, lambda: self.lbl_status.config(text=""))

        self.txt.delete("1.0", "end")
        self._refresh("")

    def _update_session_totals(self):
        self.v_st.set(f"{self.session_tokens:,}")
        self.v_sc.set(f"{self.prompt_count} prompt{'s' if self.prompt_count != 1 else ''}")
        self.v_spw.set(fmt_kwh(self.session_kwh))
        self.v_sh.set(fmt_water(self.session_water))

    def _export_csv(self):
        if not self.session_log:
            self.lbl_status.config(text="nothing to export yet")
            self.after(2000, lambda: self.lbl_status.config(text=""))
            return

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        timestamp = self.session_start.strftime("%Y-%m-%d_%H-%M")
        filename  = os.path.join(downloads, f"ATV_Session_{timestamp}.csv")

        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "prompt_num", "prompt_tokens",
                "response_tokens", "total_tokens",
                "total_kwh", "total_water_ml"
            ])
            writer.writeheader()
            writer.writerows(self.session_log)
            writer.writerow({})
            writer.writerow({
                "timestamp":       "SESSION TOTAL",
                "prompt_num":      self.prompt_count,
                "prompt_tokens":   "",
                "response_tokens": "",
                "total_tokens":    self.session_tokens,
                "total_kwh":       round(self.session_kwh, 8),
                "total_water_ml":  round(self.session_water, 4),
            })

        self.lbl_status.config(text="saved to Downloads")
        self.after(3000, lambda: self.lbl_status.config(text=""))

    def _refresh(self, text):
        if not text.strip():
            for v in (self.v_pt, self.v_rt, self.v_tt,
                      self.v_ppw, self.v_tpw, self.v_ph, self.v_th):
                v.set("--")
            self.lbl_main.config(text="paste a prompt to begin", fg=MUTED)
            self.dot_c.itemconfig(self.dot, fill=DIM)
            self.last_estimate = None
            return

        e = estimate(text)
        self.last_estimate = e
        c = indicator_color(e["total_tokens"])

        self.dot_c.itemconfig(self.dot, fill=c)
        self.lbl_main.config(text=f"{e['total_tokens']:,} tokens  (round trip)", fg=c)

        self.v_pt.set(f"{e['prompt_tokens']:,}")
        self.v_rt.set(f"~{e['response_tokens']:,}")
        self.v_tt.set(f"{e['total_tokens']:,}")
        self.v_ppw.set(fmt_kwh(e["prompt_kwh"]))
        self.v_tpw.set(fmt_kwh(e["total_kwh"]))
        self.v_ph.set(fmt_water(e["prompt_water"]))
        self.v_th.set(fmt_water(e["total_water"]))

if __name__ == "__main__":
    ATVGauge().mainloop()
