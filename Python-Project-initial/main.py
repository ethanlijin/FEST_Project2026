import tkinter as tk
from tkinter import messagebox, ttk
import os, hashlib, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# ── File paths ────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
USERS_FILE     = os.path.join(BASE_DIR, "users.csv")
STUDENTS_FILE  = os.path.join(BASE_DIR, "students.csv")
GPA_SCALE_FILE = os.path.join(BASE_DIR, "gpa_scale.json")
STUDENT_FIELDS = ["student_id", "name", "major", "course_code", "course_title", "points", "gpa"]

# ── Color palette ─────────────────────────────────────────────────────────────
BG        = "#0f172a"
PANEL     = "#111827"
CARD      = "#1e293b"
ACCENT    = "#3b82f6"
CYAN      = "#60a5fa"
TEAL      = "#2563eb"
TEXT      = "#f8fafc"
MUTED     = "#94a3b8"
GREEN     = "#22c55e"
RED       = "#ef4444"
BORDER    = "#334155"
SECONDARY = "#374151"
SIDEBAR_BUTTON_BG = "#f8fafc"
SIDEBAR_BUTTON_HOVER = "#e2e8f0"
SIDEBAR_BUTTON_TEXT = "#111827"

OPTION_COLORS = [
    ACCENT, ACCENT, RED, ACCENT, ACCENT,
    ACCENT, ACCENT, ACCENT, ACCENT, ACCENT,
]
OPTION_LABELS = [
    "Add Student", "Edit Student", "Delete Record",
    "GPA Formula", "Swarm Plot",  "Major Count Plot",
    "Grade Pie Chart", "Student Profile", "Student ID Card",
    "Queries",
]

# ── GPA grading scale ─────────────────────────────────────────────────────────
DEFAULT_GPA_SCALE = [
    (97, 100, "A+", 4.0), (93, 96, "A",  4.0), (90, 92, "A-", 3.7),
    (87,  89, "B+", 3.3), (83, 86, "B",  3.0), (80, 82, "B-", 2.7),
    (77,  79, "C+", 2.3), (73, 76, "C",  2.0), (70, 72, "C-", 1.7),
    (67,  69, "D+", 1.3), (63, 66, "D",  1.0), (60, 62, "D-", 0.7),
    ( 0,  59, "F",  0.0),
]
GPA_SCALE = list(DEFAULT_GPA_SCALE)

GRADE_PALETTE = {
    "A (90-100)": "#10b981",
    "B (80-89)":  "#3b82f6",
    "C (70-79)":  "#f59e0b",
    "D (60-69)":  "#f97316",
    "F (0-59)":   "#ef4444",
}

# ── App-level state ───────────────────────────────────────────────────────────
root         = None
current_user = None
delete_undo_state = None
undo_delete_button = None
dashboard_stat_vars = {}


# =============================================================================
#  GPA helpers
# =============================================================================

def points_to_grade(pts):
    p = max(0, min(100, round(float(pts))))
    for lo, hi, letter, gpa in GPA_SCALE:
        if lo <= p <= hi:
            return letter, gpa
    return "F", 0.0


def grade_category(p):
    p = float(p)
    if p >= 90: return "A (90-100)"
    if p >= 80: return "B (80-89)"
    if p >= 70: return "C (70-79)"
    if p >= 60: return "D (60-69)"
    return "F (0-59)"


# =============================================================================
#  CSV helpers — users
# =============================================================================

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        # dtype=str + keep_default_na=False: keep every value as plain text,
        # exactly like csv.DictReader used to (otherwise pandas would try to
        # infer numeric ids and turn blank fields into NaN).
        df = pd.read_csv(USERS_FILE, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return {}
    return dict(zip(df["id"], df["password"]))


def save_user(uid, hpw):
    exists = os.path.exists(USERS_FILE)
    row = pd.DataFrame([{"id": uid, "password": hpw}])
    row.to_csv(USERS_FILE, mode="a", header=not exists, index=False)


# =============================================================================
#  GPA scale persistence
# =============================================================================

def load_gpa_scale():
    global GPA_SCALE
    if os.path.exists(GPA_SCALE_FILE):
        try:
            with open(GPA_SCALE_FILE) as f:
                data = json.load(f)
            GPA_SCALE = [tuple(row) for row in data]
        except Exception:
            GPA_SCALE = list(DEFAULT_GPA_SCALE)


def save_gpa_scale():
    with open(GPA_SCALE_FILE, "w") as f:
        json.dump(GPA_SCALE, f, indent=2)


# =============================================================================
#  CSV helpers — students
# =============================================================================

def load_students():
    if not os.path.exists(STUDENTS_FILE):
        return []
    try:
        # dtype=str + keep_default_na=False keeps student_id/points/gpa as
        # plain strings (never int64/float64/NaN), so every comparison and
        # float(...)/f"{...}" call elsewhere in the app keeps working exactly
        # as it did when the file was read with csv.DictReader.
        df = pd.read_csv(STUDENTS_FILE, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return []
    return df.to_dict("records")


def save_students(records):
    df = pd.DataFrame(records, columns=STUDENT_FIELDS)
    df.to_csv(STUDENTS_FILE, index=False)
    refresh_dashboard_stats()


def append_student(rec):
    exists = os.path.exists(STUDENTS_FILE)
    row = pd.DataFrame([rec], columns=STUDENT_FIELDS)
    row.to_csv(STUDENTS_FILE, mode="a", header=not exists, index=False)
    refresh_dashboard_stats()


def refresh_dashboard_stats():
    if not dashboard_stat_vars:
        return

    records = load_students()
    gpa_values = []
    for record in records:
        try:
            gpa_values.append(float(record["gpa"]))
        except (ValueError, TypeError):
            pass

    values = {
        "students": str(len({record["student_id"] for record in records})),
        "enrollments": str(len(records)),
        "majors": str(len({record["major"] for record in records})),
        "gpa": f"{sum(gpa_values) / len(gpa_values):.2f}" if gpa_values else "0.00",
    }
    for key, value in values.items():
        dashboard_stat_vars[key].set(value)


# =============================================================================
#  Widget factory functions
# =============================================================================

def make_label(parent, text, size=11, bold=False, color=None, **kw):
    return tk.Label(
        parent, text=text,
        font=("Segoe UI", size, "bold" if bold else "normal"),
        fg=color or TEXT, bg=parent.cget("bg"), **kw,
    )


def make_entry(parent, show="", width=32):
    wrap = tk.Frame(parent, bg=CYAN, padx=1, pady=1)
    e = tk.Entry(
        wrap, font=("Segoe UI", 13), bg=CARD, fg=TEXT,
        insertbackground=CYAN, relief="flat", width=width, show=show,
    )
    e.pack()
    return wrap, e


def make_button(parent, text, cmd, color=None, width=260, height=54, radius=26, fg="white"):
    """Canvas-based rounded-corner button."""
    color = color or ACCENT
    try:
        bg = parent.cget("bg")
    except Exception:
        bg = BG

    cv = tk.Canvas(parent, width=width, height=height,
                   bg=bg, highlightthickness=0, bd=0)

    def _draw(hover=False):
        cv.delete("all")
        r = radius
        x1, y1, x2, y2 = 1, 1, width - 1, height - 1
        c = color
        # Four corner arcs
        cv.create_arc(x1,       y1,       x1+2*r, y1+2*r, start=90,  extent=90, fill=c, outline=c)
        cv.create_arc(x2-2*r,   y1,       x2,     y1+2*r, start=0,   extent=90, fill=c, outline=c)
        cv.create_arc(x1,       y2-2*r,   x1+2*r, y2,     start=180, extent=90, fill=c, outline=c)
        cv.create_arc(x2-2*r,   y2-2*r,   x2,     y2,     start=270, extent=90, fill=c, outline=c)
        # Body fill
        cv.create_rectangle(x1+r, y1,    x2-r, y2,    fill=c, outline=c)
        cv.create_rectangle(x1,   y1+r,  x2,   y2-r,  fill=c, outline=c)
        # Hover: subtle white inner ring
        if hover:
            cv.create_arc(x1+3,     y1+3,     x1+2*r, y1+2*r, start=90,  extent=90, outline=CYAN, style="arc", width=2)
            cv.create_arc(x2-2*r,   y1+3,     x2-3,   y1+2*r, start=0,   extent=90, outline=CYAN, style="arc", width=2)
        # Label
        cv.create_text(width // 2, height // 2, text=text,
                       fill=fg, font=("Segoe UI", 13, "bold"))

    _draw()

    def on_enter(e):
        cv.config(cursor="hand2")
        _draw(hover=True)

    def on_leave(e):
        cv.config(cursor="")
        _draw()

    def on_click(e):
        if cmd:
            cmd()

    cv.bind("<Enter>",    on_enter)
    cv.bind("<Leave>",    on_leave)
    cv.bind("<Button-1>", on_click)
    return cv


def make_link(parent, text, cmd):
    return tk.Button(
        parent, text=text, command=cmd,
        font=("Segoe UI", 11, "underline"),
        fg=CYAN, bg=parent.cget("bg"),
        activeforeground=CYAN, activebackground=parent.cget("bg"),
        relief="flat", cursor="hand2", bd=0,
    )


def make_sidebar_button(parent, text, cmd, danger=False):
    color = RED if danger else SIDEBAR_BUTTON_TEXT
    return tk.Button(
        parent, text=text, command=cmd,
        font=("Segoe UI", 11, "bold"), fg=color, bg=SIDEBAR_BUTTON_BG,
        activeforeground=color, activebackground=SIDEBAR_BUTTON_HOVER,
        relief="flat", bd=0, anchor="w", padx=18, pady=9,
        cursor="hand2",
    )


def make_top_bar(title, accent=None):
    bar = tk.Frame(root, bg=PANEL)
    bar.pack(fill="x")
    tk.Frame(bar, bg=accent or ACCENT, height=5).pack(fill="x")
    make_label(bar, title, 18, bold=True).pack(pady=16)
    return bar


def make_popup(title, w=600, h=520, resizable=False):
    top = tk.Toplevel(root)
    top.title(title)
    top.geometry(f"{w}x{h}")
    top.configure(bg=BG)
    top.resizable(resizable, resizable)
    top.grab_set()
    return top


def style_treeview():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("D.Treeview",
                background=CARD, foreground=TEXT,
                fieldbackground=CARD, rowheight=30,
                font=("Segoe UI", 10))
    s.configure("D.Treeview.Heading",
                background=PANEL, foreground=CYAN,
                font=("Segoe UI", 10, "bold"))
    s.map("D.Treeview",
          background=[("selected", ACCENT)],
          foreground=[("selected", "white")])


def make_form_row(parent, label, row, show="", initial=""):
    tk.Label(parent, text=label, font=("Segoe UI", 11),
             fg=MUTED, bg=BG).grid(row=row, column=0, sticky="e", padx=(0, 12), pady=8)
    wrap = tk.Frame(parent, bg=CYAN, padx=1, pady=1)
    wrap.grid(row=row, column=1, sticky="ew", pady=8)
    e = tk.Entry(wrap, font=("Segoe UI", 12), bg=CARD, fg=TEXT,
                 insertbackground=CYAN, relief="flat", show=show, width=28)
    e.insert(0, initial)
    e.pack()
    return e


def build_treeview(parent, records, multi=False):
    style_treeview()
    cols   = ("student_id", "name", "major", "course_code", "course_title", "points", "gpa")
    heads  = ("Student ID", "Name", "Major", "Code", "Course Title", "Pts", "GPA")
    widths = (95, 130, 90, 68, 150, 48, 48)

    frame = tk.Frame(parent, bg=BG)
    frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    tree = ttk.Treeview(frame, columns=cols, show="headings",
                        style="D.Treeview", height=10,
                        selectmode="extended" if multi else "browse")
    for col, head, w in zip(cols, heads, widths):
        tree.heading(col, text=head)
        tree.column(col, width=w, anchor="center")

    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    def refresh():
        tree.delete(*tree.get_children())
        for i, r in enumerate(records):
            tree.insert("", "end", iid=str(i),
                        values=(r["student_id"], r["name"], r["major"],
                                r["course_code"], r["course_title"],
                                r["points"], r["gpa"]))
    refresh()
    return tree, refresh


# =============================================================================
#  Screen helpers
# =============================================================================

def clear_screen():
    for w in root.winfo_children():
        w.destroy()
    root.unbind("<Key>")


def footer_close_btn(parent, cmd, label="✕  Exit App"):
    """Renders a close/exit button pinned to the bottom of a screen."""
    bar = tk.Frame(parent, bg=PANEL)
    bar.pack(fill="x", side="bottom")
    tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")
    make_button(bar, label, cmd, color=SECONDARY, width=160, height=44, radius=22).pack(
        side="right", padx=24, pady=10)


def update_undo_delete_button():
    if undo_delete_button is None or not undo_delete_button.winfo_exists():
        return
    count = len(delete_undo_state["items"]) if delete_undo_state else 0
    undo_delete_button.config(
        text=f"↶  Undo delete ({count})" if count else "↶  Undo delete",
        state="normal" if count else "disabled",
    )


def undo_last_delete(parent=None):
    global delete_undo_state
    if not delete_undo_state:
        messagebox.showinfo("Nothing to Undo",
                            "There is no recent deletion to restore.",
                            parent=parent or root)
        return False

    records = load_students()
    deleted_items = delete_undo_state["items"]
    for index, record in sorted(deleted_items, key=lambda item: item[0]):
        records.insert(min(index, len(records)), record)
    save_students(records)

    restored_count = len(deleted_items)
    delete_undo_state = None
    update_undo_delete_button()
    messagebox.showinfo("Deletion Undone",
                        f"Restored {restored_count} enrollment record(s).",
                        parent=parent or root)
    return True


# =============================================================================
#  Screen: Welcome
# =============================================================================

def show_welcome():
    clear_screen()
    root.title("FEST Summer 2026")

    # Header
    hdr = tk.Frame(root, bg=PANEL, height=200)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(hdr, bg=ACCENT, height=5).pack(fill="x")
    make_label(hdr, "FEST", 60, bold=True, color=ACCENT).pack(pady=(22, 0))
    make_label(hdr, "Summer 2026  ·  Vanderbilt University", 12, color=MUTED).pack()

    # Center body
    body = tk.Frame(root, bg=BG)
    body.pack(expand=True)
    make_label(body, "Register or Login to continue", 14, color=MUTED).pack(pady=(0, 36))
    make_button(body, "   Register   ", show_register, color=ACCENT,
                width=320, height=62, radius=31).pack(pady=10)
    make_button(body, "   Login   ", show_login, color=TEAL,
                width=320, height=62, radius=31).pack(pady=10)
    make_label(body, "Credentials stored in users.csv", 10, color=BORDER).pack(pady=(30, 0))

    # Footer close = quit app
    footer_close_btn(root, root.destroy, label="✕  Quit App")


# =============================================================================
#  Screen: Register
# =============================================================================

def show_register():
    clear_screen()
    root.title("FEST — Register")
    make_top_bar("Create Account", ACCENT)

    body = tk.Frame(root, bg=BG)
    body.pack(expand=True)

    make_label(body, "User ID", 11, color=MUTED).pack(anchor="w")
    id_f, r_id = make_entry(body)
    id_f.pack(pady=(4, 14), fill="x")

    make_label(body, "Password", 11, color=MUTED).pack(anchor="w")
    pw_f, r_pw = make_entry(body, show="●")
    pw_f.pack(pady=(4, 14), fill="x")

    make_label(body, "Confirm Password", 11, color=MUTED).pack(anchor="w")
    pw2_f, r_pw2 = make_entry(body, show="●")
    pw2_f.pack(pady=(4, 28), fill="x")

    def do_register():
        uid = r_id.get().strip()
        pw  = r_pw.get()
        pw2 = r_pw2.get()
        if not uid or not pw:
            messagebox.showerror("Error", "ID and password are required.")
            return
        if len(pw) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters.")
            return
        if pw != pw2:
            messagebox.showerror("Error", "Passwords do not match.")
            return
        if uid in load_users():
            messagebox.showerror("Error", f"ID '{uid}' is already taken.")
            return
        save_user(uid, hash_password(pw))
        messagebox.showinfo("Success", f"Account '{uid}' created!\nYou can now log in.")
        show_login()

    make_button(body, "Register", do_register, color=ACCENT,
                width=280, height=58, radius=29).pack(pady=6)

    row = tk.Frame(body, bg=BG)
    row.pack(pady=(18, 0))
    make_label(row, "Already registered?", 11, color=MUTED).pack(side="left")
    make_link(row, "  Login", show_login).pack(side="left")

    r_pw2.bind("<Return>", lambda _: do_register())

    # Footer close = back to welcome
    footer_close_btn(root, show_welcome, label="←  Back to Home")


# =============================================================================
#  Screen: Login
# =============================================================================

def show_login():
    clear_screen()
    root.title("FEST — Login")
    make_top_bar("Sign In", CYAN)

    body = tk.Frame(root, bg=BG)
    body.pack(expand=True)

    make_label(body, "User ID", 11, color=MUTED).pack(anchor="w")
    id_f, l_id = make_entry(body)
    id_f.pack(pady=(4, 14), fill="x")

    make_label(body, "Password", 11, color=MUTED).pack(anchor="w")
    pw_f, l_pw = make_entry(body, show="●")
    pw_f.pack(pady=(4, 30), fill="x")

    def do_login():
        global current_user
        uid = l_id.get().strip()
        pw  = l_pw.get()
        if not uid or not pw:
            messagebox.showerror("Error", "Enter your ID and password.")
            return
        users = load_users()
        if uid not in users or users[uid] != hash_password(pw):
            messagebox.showerror("Login Failed", "Invalid ID or password.")
            return
        current_user = uid
        show_menu()

    make_button(body, "Login", do_login, color=TEAL,
                width=280, height=58, radius=29).pack(pady=6)
    l_pw.bind("<Return>", lambda _: do_login())

    row = tk.Frame(body, bg=BG)
    row.pack(pady=(18, 0))
    make_label(row, "No account?", 11, color=MUTED).pack(side="left")
    make_link(row, "  Register here", show_register).pack(side="left")

    # Footer close = back to welcome
    footer_close_btn(root, show_welcome, label="←  Back to Home")


# =============================================================================
#  Screen: Main Menu
# =============================================================================

def show_menu():
    global dashboard_stat_vars, undo_delete_button
    clear_screen()
    root.title(f"FEST Student Manager — {current_user}")

    shell = tk.Frame(root, bg=BG)
    shell.pack(fill="both", expand=True)

    sidebar = tk.Frame(shell, bg=PANEL, width=245)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    brand = tk.Frame(sidebar, bg=PANEL)
    brand.pack(fill="x", padx=18, pady=(22, 16))
    make_label(brand, "FEST", 26, bold=True, color=ACCENT).pack(anchor="w")
    make_label(brand, "Student Manager", 10, color=MUTED).pack(anchor="w")

    tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=14, pady=(0, 10))

    make_label(sidebar, "STUDENTS", 9, bold=True, color=MUTED).pack(
        anchor="w", padx=18, pady=(4, 2))
    for label, option, danger in [
        ("＋  Add student", 0, False),
        ("✎  Edit records", 1, False),
        ("⌫  Delete records", 2, True),
        ("▤  Student profiles", 7, False),
        ("▣  Student ID cards", 8, False),
    ]:
        make_sidebar_button(
            sidebar, label, lambda n=option: handle_option(n), danger=danger
        ).pack(fill="x", padx=8)

    make_label(sidebar, "ACADEMICS", 9, bold=True, color=MUTED).pack(
        anchor="w", padx=18, pady=(14, 2))
    for label, option in [
        ("ƒ  GPA scale", 3),
        ("•  Score distribution", 4),
        ("▥  Major enrollment", 5),
        ("◕  Grade distribution", 6),
        ("?  Academic queries", 9),
    ]:
        make_sidebar_button(
            sidebar, label, lambda n=option: handle_option(n)
        ).pack(fill="x", padx=8)

    undo_delete_button = tk.Button(
        sidebar, text="↶  Undo delete", command=undo_last_delete,
        font=("Segoe UI", 10, "bold"), fg=SIDEBAR_BUTTON_TEXT,
        bg=SIDEBAR_BUTTON_BG, activeforeground=SIDEBAR_BUTTON_TEXT,
        activebackground=SIDEBAR_BUTTON_HOVER,
        disabledforeground="#64748b", relief="flat", bd=0,
        anchor="w", padx=16, pady=9, cursor="hand2",
    )
    undo_delete_button.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
    update_undo_delete_button()

    account = tk.Frame(sidebar, bg=PANEL)
    account.pack(fill="x", side="bottom", padx=12, pady=(8, 10))
    tk.Frame(account, bg=BORDER, height=1).pack(fill="x", pady=(0, 10))
    make_label(account, current_user, 10, bold=True).pack(anchor="w", padx=6)
    make_label(account, "Signed in", 9, color=MUTED).pack(anchor="w", padx=6)
    make_sidebar_button(account, "Log out", do_logout).pack(fill="x", pady=(5, 0))

    content = tk.Frame(shell, bg=BG)
    content.pack(side="left", fill="both", expand=True)

    header = tk.Frame(content, bg=BG)
    header.pack(fill="x", padx=34, pady=(28, 12))
    make_label(header, "Dashboard", 26, bold=True).pack(anchor="w")
    make_label(header, "Manage students and review academic performance.",
               11, color=MUTED).pack(anchor="w", pady=(4, 0))

    dashboard_stat_vars = {
        "students": tk.StringVar(),
        "enrollments": tk.StringVar(),
        "majors": tk.StringVar(),
        "gpa": tk.StringVar(),
    }
    refresh_dashboard_stats()

    stats = tk.Frame(content, bg=BG)
    stats.pack(fill="x", padx=28, pady=12)
    for column in range(4):
        stats.columnconfigure(column, weight=1)

    for column, (key, label) in enumerate([
        ("students", "Students"),
        ("enrollments", "Enrollments"),
        ("majors", "Majors"),
        ("gpa", "Average GPA"),
    ]):
        card = tk.Frame(stats, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        make_label(card, "", 24, bold=True, color=ACCENT,
                   textvariable=dashboard_stat_vars[key]).pack(
            anchor="w", padx=18, pady=(16, 2))
        make_label(card, label, 10, color=MUTED).pack(
            anchor="w", padx=18, pady=(0, 16))

    workspace = tk.Frame(content, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
    workspace.pack(fill="both", expand=True, padx=34, pady=(16, 34))
    make_label(workspace, "Quick actions", 17, bold=True).pack(
        anchor="w", padx=24, pady=(22, 4))
    make_label(workspace,
               "Use the sidebar for all tools, or start with a common task.",
               10, color=MUTED).pack(anchor="w", padx=24)

    quick_actions = tk.Frame(workspace, bg=CARD)
    quick_actions.pack(anchor="w", padx=16, pady=22)
    make_button(quick_actions, "Add Student", opt_add_student,
                color=ACCENT, width=180, height=50, radius=12).pack(
                    side="left", padx=8)
    make_button(quick_actions, "Edit Records", opt_edit_student,
                color=SECONDARY, width=180, height=50, radius=12).pack(
                    side="left", padx=8)
    make_button(quick_actions, "View Profiles", opt_student_profile,
                color=SECONDARY, width=180, height=50, radius=12).pack(
                    side="left", padx=8)

    def handle_keyboard_shortcut(event):
        if len(event.char) == 1 and event.char in "0123456789":
            handle_option(int(event.char))

    root.bind("<Key>", handle_keyboard_shortcut)


def handle_option(n):
    dispatch = {
        0: opt_add_student,
        1: opt_edit_student,
        2: opt_delete_student,
        3: opt_gpa_formula,
        4: opt_swarm_plot,
        5: opt_countplot,
        6: opt_piechart,
        7: opt_student_profile,
        8: opt_student_id_card,
        9: opt_queries,
    }
    dispatch.get(n, lambda: None)()


def do_logout():
    global current_user
    current_user = None
    show_welcome()


# =============================================================================
#  Option 0: Add Student
# =============================================================================

def opt_add_student():
    top = make_popup("Add New Student", w=560, h=560)
    tk.Frame(top, bg=OPTION_COLORS[0], height=5).pack(fill="x")
    make_label(top, "Add New Student Record", 15, bold=True).pack(pady=12)

    form = tk.Frame(top, bg=BG)
    form.pack(padx=36)
    form.columnconfigure(1, weight=1)

    field_defs = [
        ("Student ID",     ""),
        ("Full Name",      ""),
        ("Major",          ""),
        ("Course Code",    ""),
        ("Course Title",   ""),
        ("Points (0–100)", ""),
    ]
    entries = [make_form_row(form, lbl, i, initial=init)
               for i, (lbl, init) in enumerate(field_defs)]
    sid_e, name_e, major_e, code_e, title_e, pts_e = entries

    gpa_var = tk.StringVar(value="—")
    tk.Label(form, text="Grade / GPA", font=("Segoe UI", 11),
             fg=MUTED, bg=BG).grid(row=6, column=0, sticky="e", padx=(0, 12), pady=8)
    tk.Label(form, textvariable=gpa_var, font=("Segoe UI", 12, "bold"),
             fg=GREEN, bg=BG).grid(row=6, column=1, sticky="w")

    def update_gpa(*_):
        try:
            letter, gpa = points_to_grade(pts_e.get())
            gpa_var.set(f"{letter}  /  {gpa:.1f}")
        except (ValueError, TypeError):
            gpa_var.set("—")

    pts_e.bind("<KeyRelease>", update_gpa)

    def do_add():
        text_vals = [e.get().strip() for e in entries[:-1]]
        if not all(text_vals):
            messagebox.showerror("Error", "All fields are required.", parent=top)
            return
        try:
            pts = float(pts_e.get())
            assert 0 <= pts <= 100
        except (ValueError, AssertionError):
            messagebox.showerror("Error", "Points must be a number 0–100.", parent=top)
            return
        letter, gpa = points_to_grade(pts)
        append_student({
            "student_id":   text_vals[0], "name":  text_vals[1],
            "major":        text_vals[2], "course_code":  text_vals[3],
            "course_title": text_vals[4], "points": f"{pts:.1f}",
            "gpa":          f"{gpa:.1f}",
        })
        messagebox.showinfo("Saved",
                            f"Student '{text_vals[1]}' added.\nGrade: {letter}  |  GPA: {gpa:.1f}",
                            parent=top)
        for e in entries:
            e.delete(0, "end")
        gpa_var.set("—")

    btn_row = tk.Frame(top, bg=BG)
    btn_row.pack(pady=16)
    make_button(btn_row, "Add Student", do_add,
                color=ACCENT, width=200, height=52, radius=26).pack(side="left", padx=8)
    make_button(btn_row, "Close", top.destroy,
                color=SECONDARY, width=130, height=52, radius=26).pack(side="left", padx=8)


# =============================================================================
#  Option 1: Edit Student
# =============================================================================

def opt_edit_student():
    top = make_popup("Edit Student Record", w=820, h=600)
    tk.Frame(top, bg=OPTION_COLORS[1], height=5).pack(fill="x")
    make_label(top, "Edit Student Record", 15, bold=True).pack(pady=10)

    records = load_students()
    tree, refresh_tree = build_treeview(top, records)

    def open_edit_form():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a row to edit.", parent=top)
            return
        idx = int(sel[0])
        rec = records[idx]

        win = tk.Toplevel(top)
        win.title("Edit Record")
        win.geometry("520x490")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()
        tk.Frame(win, bg=OPTION_COLORS[1], height=5).pack(fill="x")
        make_label(win, "Edit Record", 14, bold=True).pack(pady=10)

        form = tk.Frame(win, bg=BG)
        form.pack(padx=32)
        form.columnconfigure(1, weight=1)

        field_defs = [
            ("Student ID",     "student_id"),
            ("Full Name",      "name"),
            ("Major",          "major"),
            ("Course Code",    "course_code"),
            ("Course Title",   "course_title"),
            ("Points (0–100)", "points"),
        ]
        entries = {key: make_form_row(form, lbl, i, initial=rec[key])
                   for i, (lbl, key) in enumerate(field_defs)}

        gpa_var = tk.StringVar(value=rec.get("gpa", "—"))
        tk.Label(form, text="Grade / GPA", font=("Segoe UI", 11),
                 fg=MUTED, bg=BG).grid(
                     row=len(field_defs), column=0, sticky="e", padx=(0, 12), pady=8)
        tk.Label(form, textvariable=gpa_var, font=("Segoe UI", 12, "bold"),
                 fg=GREEN, bg=BG).grid(row=len(field_defs), column=1, sticky="w")

        def update_gpa(*_):
            try:
                letter, gpa = points_to_grade(entries["points"].get())
                gpa_var.set(f"{letter}  /  {gpa:.1f}")
            except (ValueError, TypeError):
                gpa_var.set("—")

        entries["points"].bind("<KeyRelease>", update_gpa)
        update_gpa()

        def do_save():
            text_vals = {k: entries[k].get().strip()
                         for k in entries if k != "points"}
            if not all(text_vals.values()):
                messagebox.showerror("Error", "All fields are required.", parent=win)
                return
            try:
                pts = float(entries["points"].get())
                assert 0 <= pts <= 100
            except (ValueError, AssertionError):
                messagebox.showerror("Error", "Points must be 0–100.", parent=win)
                return
            letter, gpa = points_to_grade(pts)
            records[idx] = {
                "student_id":   text_vals["student_id"],
                "name":         text_vals["name"],
                "major":        text_vals["major"],
                "course_code":  text_vals["course_code"],
                "course_title": text_vals["course_title"],
                "points":       f"{pts:.1f}",
                "gpa":          f"{gpa:.1f}",
            }
            save_students(records)
            refresh_tree()
            messagebox.showinfo("Saved", "Record updated.", parent=win)
            win.destroy()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=14)
        make_button(btn_row, "Save Changes", do_save,
                    color=GREEN, width=200, height=52, radius=26).pack(side="left", padx=8)
        make_button(btn_row, "Cancel", win.destroy,
                    color=SECONDARY, width=130, height=52, radius=26).pack(side="left", padx=8)

    btn_row = tk.Frame(top, bg=BG)
    btn_row.pack(pady=10)
    make_button(btn_row, "Edit Selected", open_edit_form,
                color=OPTION_COLORS[1], width=200, height=52, radius=26).pack(side="left", padx=8)
    make_button(btn_row, "Close", top.destroy,
                color=SECONDARY, width=130, height=52, radius=26).pack(side="left", padx=8)


# =============================================================================
#  Option 2: Delete Student
# =============================================================================

def opt_delete_student():
    top = make_popup("Delete Student Records", w=820, h=560)
    tk.Frame(top, bg=RED, height=5).pack(fill="x")
    make_label(top, "Delete Student Records", 15, bold=True).pack(pady=10)
    make_label(top,
               "Select carefully. The most recent deletion can be restored with Undo.",
               11, color=MUTED).pack()

    records = load_students()
    tree, refresh_tree = build_treeview(top, records, multi=True)

    def do_delete():
        global delete_undo_state
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select at least one record.", parent=top)
            return
        indices = sorted({int(item) for item in sel})
        selected_records = [(index, dict(records[index])) for index in indices]
        preview_lines = [
            f"• {record['name']} — {record['course_code']}"
            for _, record in selected_records[:5]
        ]
        if len(selected_records) > 5:
            preview_lines.append(f"• …and {len(selected_records) - 5} more")
        preview = "\n".join(preview_lines)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete {len(indices)} enrollment record(s)?\n\n"
            f"{preview}\n\n"
            "You can undo this deletion during the current session.",
            parent=top,
        ):
            return
        delete_undo_state = {"items": selected_records}
        new_recs = [r for i, r in enumerate(records) if i not in set(indices)]
        records.clear()
        records.extend(new_recs)
        save_students(records)
        refresh_tree()
        update_undo_delete_button()
        messagebox.showinfo(
            "Records Deleted",
            f"{len(indices)} record(s) removed.\n"
            "Choose Undo here or in the sidebar to restore them.",
            parent=top,
        )

    def do_undo():
        if undo_last_delete(top):
            records.clear()
            records.extend(load_students())
            refresh_tree()

    btn_row = tk.Frame(top, bg=BG)
    btn_row.pack(pady=12)
    make_button(btn_row, "Delete Selected", do_delete,
                color=RED, width=210, height=52, radius=26).pack(side="left", padx=8)
    make_button(btn_row, "Undo Delete", do_undo,
                color=SECONDARY, width=160, height=52, radius=26).pack(side="left", padx=8)
    make_button(btn_row, "Close", top.destroy,
                color=SECONDARY, width=130, height=52, radius=26).pack(side="left", padx=8)


# =============================================================================
#  Option 3: GPA Formula (editable table)
# =============================================================================

def opt_gpa_formula():
    top = make_popup("GPA Grading Scale", w=560, h=720)
    tk.Frame(top, bg=OPTION_COLORS[3], height=5).pack(fill="x")
    make_label(top, "GPA Calculation Scale", 15, bold=True).pack(pady=(10, 2))
    make_label(top, "Select a row, edit Min / Max, then click Save Row",
               11, color=MUTED).pack()

    # ── Treeview ──────────────────────────────────────────────────────────────
    style_treeview()
    tree_frame = tk.Frame(top, bg=BG)
    tree_frame.pack(fill="both", expand=True, padx=18, pady=(10, 4))

    tree = ttk.Treeview(tree_frame, columns=("range", "letter", "gpa"),
                        show="headings", style="D.Treeview", height=13)
    for col, head, w in [("range",  "Points Range", 180),
                          ("letter", "Letter Grade",  150),
                          ("gpa",    "GPA Points",    140)]:
        tree.heading(col, text=head)
        tree.column(col, width=w, anchor="center")
    tree.pack(fill="both", expand=True)

    def refresh_tree():
        tree.delete(*tree.get_children())
        for i, (lo, hi, letter, gpa) in enumerate(GPA_SCALE):
            tree.insert("", "end", iid=str(i),
                        values=(f"{lo} – {hi}", letter, f"{gpa:.1f}"))

    refresh_tree()

    # ── Edit panel ────────────────────────────────────────────────────────────
    edit_panel = tk.Frame(top, bg=PANEL)
    edit_panel.pack(fill="x", padx=18, pady=8)
    tk.Frame(edit_panel, bg=OPTION_COLORS[3], height=2).pack(fill="x")

    info_row = tk.Frame(edit_panel, bg=PANEL)
    info_row.pack(fill="x", padx=14, pady=(10, 4))
    make_label(info_row, "Selected:", 11, color=MUTED).pack(side="left")

    letter_var = tk.StringVar(value="—")
    make_label(info_row, "  Grade:", 11, color=MUTED).pack(side="left")
    tk.Label(info_row, textvariable=letter_var, font=("Segoe UI", 12, "bold"),
             fg=CYAN, bg=PANEL).pack(side="left", padx=(3, 16))

    gpa_lbl_var = tk.StringVar(value="—")
    make_label(info_row, "GPA pts:", 11, color=MUTED).pack(side="left")
    tk.Label(info_row, textvariable=gpa_lbl_var, font=("Segoe UI", 12, "bold"),
             fg=GREEN, bg=PANEL).pack(side="left", padx=(3, 0))

    input_row = tk.Frame(edit_panel, bg=PANEL)
    input_row.pack(fill="x", padx=14, pady=(4, 12))

    make_label(input_row, "Min pts:", 11, color=MUTED).pack(side="left")
    min_wrap = tk.Frame(input_row, bg=CYAN, padx=1, pady=1)
    min_wrap.pack(side="left", padx=(6, 16))
    min_e = tk.Entry(min_wrap, font=("Segoe UI", 12), bg=CARD, fg=TEXT,
                     insertbackground=CYAN, relief="flat", width=5)
    min_e.pack()

    make_label(input_row, "Max pts:", 11, color=MUTED).pack(side="left")
    max_wrap = tk.Frame(input_row, bg=CYAN, padx=1, pady=1)
    max_wrap.pack(side="left", padx=(6, 20))
    max_e = tk.Entry(max_wrap, font=("Segoe UI", 12), bg=CARD, fg=TEXT,
                     insertbackground=CYAN, relief="flat", width=5)
    max_e.pack()

    selected_idx = [None]

    def on_select(event):
        sel = tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        selected_idx[0] = idx
        lo, hi, letter, gpa = GPA_SCALE[idx]
        letter_var.set(letter)
        gpa_lbl_var.set(f"{gpa:.1f}")
        min_e.delete(0, "end"); min_e.insert(0, str(lo))
        max_e.delete(0, "end"); max_e.insert(0, str(hi))

    tree.bind("<<TreeviewSelect>>", on_select)

    def save_row():
        idx = selected_idx[0]
        if idx is None:
            messagebox.showwarning("Select", "Select a row first.", parent=top)
            return
        try:
            lo = int(min_e.get().strip())
            hi = int(max_e.get().strip())
            assert 0 <= lo <= 100 and 0 <= hi <= 100 and lo <= hi
        except (ValueError, AssertionError):
            messagebox.showerror("Invalid Input",
                                 "Min and Max must be whole numbers 0–100, with Min ≤ Max.",
                                 parent=top)
            return
        _, _, letter, gpa = GPA_SCALE[idx]
        GPA_SCALE[idx] = (lo, hi, letter, gpa)
        save_gpa_scale()
        refresh_tree()
        tree.selection_set(str(idx))
        messagebox.showinfo("Saved", f"Range for {letter} updated to {lo} – {hi}.", parent=top)

    def reset_defaults():
        if not messagebox.askyesno("Reset", "Reset all ranges back to defaults?", parent=top):
            return
        GPA_SCALE.clear()
        GPA_SCALE.extend(DEFAULT_GPA_SCALE)
        save_gpa_scale()
        refresh_tree()
        selected_idx[0] = None
        letter_var.set("—"); gpa_lbl_var.set("—")
        min_e.delete(0, "end"); max_e.delete(0, "end")
        messagebox.showinfo("Reset", "Grading scale reset to defaults.", parent=top)

    make_button(input_row, "Save Row", save_row,
                color=GREEN, width=130, height=44, radius=22).pack(side="left", padx=4)
    make_button(input_row, "Reset Defaults", reset_defaults,
                color=SECONDARY, width=170, height=44, radius=22).pack(side="left", padx=4)

    # ── Footer ────────────────────────────────────────────────────────────────
    make_label(top, "Cumulative GPA = Σ(GPA × credit hrs) ÷ Σ(credit hrs)",
               11, color=CYAN).pack(pady=(6, 2))
    make_button(top, "Close", top.destroy,
                color=SECONDARY, width=150, height=50, radius=25).pack(pady=8)


# =============================================================================
#  Option 4: Swarm Plot
# =============================================================================

def opt_swarm_plot():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    try:
        pts = [float(r["points"]) for r in records]
    except ValueError:
        messagebox.showerror("Data Error", "Some records have invalid points values.")
        return

    top = make_popup("Swarm Plot — Student Scores", w=960, h=660, resizable=True)
    tk.Frame(top, bg=OPTION_COLORS[4], height=5).pack(fill="x")

    codes = [r["course_code"] for r in records]
    cats  = [grade_category(p) for p in pts]

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(CARD)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.tick_params(colors="#94a3b8")
    ax.set_title("Student Score Distribution (Swarm Plot)",
                 color="#f1f5f9", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Course Code", color="#94a3b8", fontsize=11, labelpad=8)
    ax.set_ylabel("Points (out of 100)", color="#94a3b8", fontsize=11)
    ax.set_ylim(-5, 108)

    if HAS_SEABORN:
        df = pd.DataFrame({"Points": pts, "Course": codes, "Grade": cats})
        sns.swarmplot(data=df, x="Course", y="Points", hue="Grade",
                      palette=GRADE_PALETTE, ax=ax, size=9,
                      linewidth=0.5, edgecolor=BG,
                      hue_order=list(GRADE_PALETTE.keys()))
        leg = ax.get_legend()
        if leg:
            leg.get_frame().set_facecolor(PANEL)
            leg.get_frame().set_edgecolor(BORDER)
            leg.set_title("Grade", prop={"size": 9})
            leg.get_title().set_color("#94a3b8")
            for t in leg.get_texts():
                t.set_color("#f1f5f9")
    else:
        unique = sorted(set(codes))
        x_map  = {c: i for i, c in enumerate(unique)}
        rng    = np.random.default_rng(42)
        xs     = [x_map[c] + rng.uniform(-0.25, 0.25) for c in codes]
        colors = [GRADE_PALETTE[g] for g in cats]
        ax.scatter(xs, pts, c=colors, s=90, alpha=0.9,
                   edgecolors=BG, linewidths=0.5)
        ax.set_xticks(range(len(unique)))
        ax.set_xticklabels(unique, color="#94a3b8")
        from matplotlib.patches import Patch
        handles = [Patch(facecolor=c, label=l) for l, c in GRADE_PALETTE.items()]
        leg = ax.legend(handles=handles, facecolor=PANEL, edgecolor=BORDER)
        for t in leg.get_texts():
            t.set_color("#f1f5f9")

    for threshold, color in [(90, "#10b981"), (80, "#3b82f6"),
                              (70, "#f59e0b"), (60, "#f97316")]:
        ax.axhline(threshold, color=color, linewidth=0.7, linestyle="--", alpha=0.45)

    plt.tight_layout(pad=1.5)

    toolbar_frame = tk.Frame(top, bg=PANEL)
    toolbar_frame.pack(fill="x", side="bottom")

    def on_close():
        plt.close(fig)
        top.destroy()

    make_button(toolbar_frame, "Close", on_close,
                color=SECONDARY, width=120, height=42, radius=21).pack(
                    side="right", padx=12, pady=6)

    canvas = FigureCanvasTkAgg(fig, master=top)
    NavigationToolbar2Tk(canvas, toolbar_frame).update()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    canvas.draw()

    top.protocol("WM_DELETE_WINDOW", on_close)


# =============================================================================
#  Option 5: Major Count Plot
# =============================================================================

def opt_countplot():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    top = make_popup("Count Plot — Students per Major", w=960, h=660, resizable=True)
    tk.Frame(top, bg=OPTION_COLORS[5], height=5).pack(fill="x")

    major_counts = {}
    for r in records:
        major = r["major"].strip()
        major_counts[major] = major_counts.get(major, 0) + 1

    majors = list(major_counts.keys())
    counts = [major_counts[m] for m in majors]

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(CARD)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.tick_params(colors="#94a3b8")
    ax.set_title("Number of Students per Major",
                 color="#f1f5f9", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Major", color="#94a3b8", fontsize=11, labelpad=8)
    ax.set_ylabel("Number of Students", color="#94a3b8", fontsize=11)

    if HAS_SEABORN:
        df = pd.DataFrame({"Major": majors, "Count": counts})
        df = df.sort_values("Count", ascending=False)
        sns.barplot(data=df, x="Major", y="Count", palette="viridis",
                    ax=ax, edgecolor=BG, linewidth=0.8)
        for bar, count in zip(ax.patches, df["Count"]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    str(count), ha="center", va="bottom",
                    color="#f1f5f9", fontsize=11, fontweight="bold")
    else:
        bar_colors = [ACCENT, CYAN, TEAL, GREEN, "#f59e0b"]
        bars = ax.bar(majors, counts,
                      color=[bar_colors[i % len(bar_colors)] for i in range(len(majors))],
                      edgecolor=BG, linewidth=0.8)
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    str(count), ha="center", va="bottom",
                    color="#f1f5f9", fontsize=11, fontweight="bold")
        ax.set_xticks(range(len(majors)))
        ax.set_xticklabels(majors, color="#94a3b8")

    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, max(counts) + 1.5)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout(pad=1.5)

    toolbar_frame = tk.Frame(top, bg=PANEL)
    toolbar_frame.pack(fill="x", side="bottom")

    def on_close():
        plt.close(fig)
        top.destroy()

    make_button(toolbar_frame, "Close", on_close,
                color=SECONDARY, width=120, height=42, radius=21).pack(
                    side="right", padx=12, pady=6)

    canvas = FigureCanvasTkAgg(fig, master=top)
    NavigationToolbar2Tk(canvas, toolbar_frame).update()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    canvas.draw()

    top.protocol("WM_DELETE_WINDOW", on_close)


# =============================================================================
#  Option 6: Grade Pie Chart
# =============================================================================

def opt_piechart():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    top = make_popup("Pie Chart — Grade Distribution", w=1000, h=780, resizable=True)
    tk.Frame(top, bg=OPTION_COLORS[6], height=5).pack(fill="x")

    # Count each letter grade (use first letter: A, B, C, D, F)
    grade_counts = {}
    for r in records:
        try:
            letter, _ = points_to_grade(float(r["points"]))
            key = letter[0]          # collapse A+/A/A- → "A", etc.
        except (ValueError, TypeError):
            key = "F"
        grade_counts[key] = grade_counts.get(key, 0) + 1

    # Preserve meaningful order
    ordered_keys = [k for k in ["A", "B", "C", "D", "F"] if k in grade_counts]
    labels  = [f"Grade {k}" for k in ordered_keys]
    sizes   = [grade_counts[k] for k in ordered_keys]
    colors  = {
        "A": "#10b981",   # green
        "B": "#3b82f6",   # blue
        "C": "#f59e0b",   # amber
        "D": "#f97316",   # orange
        "F": "#ef4444",   # red
    }
    pie_colors  = [colors[k] for k in ordered_keys]
    # Only pull out the single largest slice, keep the rest flush.
    explode_idx = sizes.index(max(sizes))
    explode     = [0.08 if i == explode_idx else 0 for i in range(len(sizes))]

    fig, ax = plt.subplots(figsize=(9.8, 7.0))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    def _darken(hex_color, factor=0.55):
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── fake "3D" extrusion ────────────────────────────────────────────────
    # Matplotlib has no native 3D pie, so we fake the depth/shading by
    # stacking darker copies of the pie underneath, each nudged a hair
    # further down. The real (bright) pie drawn on top covers all but a
    # thin sliver of each layer, giving the wedges a beveled, extruded look.
    shade_colors = [_darken(c) for c in pie_colors]
    DEPTH_LAYERS = 14
    DEPTH_STEP   = 0.012
    for layer in range(DEPTH_LAYERS, 0, -1):
        ax.pie(
            sizes,
            explode=explode,
            colors=shade_colors,
            startangle=140,
            center=(0, -DEPTH_STEP * layer),
            radius=1,
            wedgeprops={"edgecolor": "none"},
        )

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%\n({round(pct * sum(sizes) / 100)})",
        colors=pie_colors,
        explode=explode,
        startangle=140,
        shadow=True,
        wedgeprops={"edgecolor": BG, "linewidth": 2},
        pctdistance=0.72,
        textprops={"fontsize": 11},
    )
    ax.set_ylim(-1.2 - DEPTH_STEP * DEPTH_LAYERS, 1.2)

    # Style percentage text
    for at in autotexts:
        at.set_color("#f1f5f9")
        at.set_fontweight("bold")
        at.set_fontsize(10)

    # Custom legend with count info
    legend_labels = [f"Grade {k}  ({grade_counts[k]} student{'s' if grade_counts[k] != 1 else ''})"
                     for k in ordered_keys]
    leg = ax.legend(wedges, legend_labels,
                    loc="center left",
                    bbox_to_anchor=(1.02, 0.5),
                    frameon=True,
                    framealpha=0.9,
                    facecolor=PANEL,
                    edgecolor=BORDER,
                    fontsize=11)
    for text in leg.get_texts():
        text.set_color("#f1f5f9")

    ax.set_title(f"Letter Grade Distribution  (n = {sum(sizes)} students)",
                 color="#f1f5f9", fontsize=13, fontweight="bold", pad=18)

    plt.tight_layout()

    toolbar_frame = tk.Frame(top, bg=PANEL)
    toolbar_frame.pack(fill="x", side="bottom")

    def on_close():
        plt.close(fig)
        top.destroy()

    make_button(toolbar_frame, "Close", on_close,
                color=SECONDARY, width=120, height=42, radius=21).pack(
                    side="right", padx=12, pady=6)

    canvas = FigureCanvasTkAgg(fig, master=top)
    NavigationToolbar2Tk(canvas, toolbar_frame).update()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    canvas.draw()

    top.protocol("WM_DELETE_WINDOW", on_close)


# =============================================================================
#  Option 7: Student Profile Viewer
# =============================================================================

def opt_student_profile():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    # Group records by student_id preserving insertion order
    student_dict = {}
    for r in records:
        sid = r["student_id"]
        if sid not in student_dict:
            student_dict[sid] = []
        student_dict[sid].append(r)

    student_ids  = list(student_dict.keys())
    total        = len(student_ids)
    current_idx  = [0]

    top = make_popup("Student Profile Viewer", w=760, h=640)
    top.resizable(True, True)
    tk.Frame(top, bg=OPTION_COLORS[7], height=5).pack(fill="x")

    # ── Top bar: title + search ───────────────────────────────────────────────
    topbar = tk.Frame(top, bg=PANEL)
    topbar.pack(fill="x")
    tk.Frame(topbar, bg=OPTION_COLORS[7], height=2).pack(fill="x")

    make_label(topbar, "Student Profile", 15, bold=True).pack(side="left", padx=18, pady=12)

    search_bar = tk.Frame(topbar, bg=PANEL)
    search_bar.pack(side="right", padx=18, pady=10)

    make_label(search_bar, "Search ID:", 11, color=MUTED).pack(side="left", padx=(0, 6))
    srch_wrap = tk.Frame(search_bar, bg=CYAN, padx=1, pady=1)
    srch_wrap.pack(side="left")
    srch_entry = tk.Entry(srch_wrap, font=("Segoe UI", 11), bg=CARD, fg=TEXT,
                          insertbackground=CYAN, relief="flat", width=14)
    srch_entry.pack()

    def do_search():
        sid = srch_entry.get().strip()
        if not sid:
            return
        if sid in student_dict:
            show_student(student_ids.index(sid))
        else:
            messagebox.showwarning("Not Found",
                                   f"Student ID  '{sid}'  not found.", parent=top)

    make_button(search_bar, "Search", do_search,
                color=OPTION_COLORS[7], width=110, height=38, radius=19).pack(
                    side="left", padx=(8, 0))
    srch_entry.bind("<Return>", lambda _: do_search())

    # ── Profile card ──────────────────────────────────────────────────────────
    card = tk.Frame(top, bg=PANEL, padx=24, pady=18)
    card.pack(fill="x", padx=20, pady=(14, 6))
    tk.Frame(card, bg=OPTION_COLORS[7], height=3).pack(fill="x", pady=(0, 12))

    id_var    = tk.StringVar()
    name_var  = tk.StringVar()
    major_var = tk.StringVar()

    def info_row(icon, var, fg_color):
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=icon, font=("Segoe UI", 14, "bold"),
                 fg=MUTED, bg=PANEL, width=3, anchor="w").pack(side="left")
        tk.Label(row, textvariable=var, font=("Segoe UI", 14, "bold"),
                 fg=fg_color, bg=PANEL, anchor="w").pack(side="left")

    info_row("ID", id_var,    CYAN)
    info_row("👤", name_var,  TEXT)
    info_row("📚", major_var, "#a78bfa")

    # ── Course table ──────────────────────────────────────────────────────────
    tbl_hdr = tk.Frame(top, bg=BG)
    tbl_hdr.pack(fill="x", padx=20, pady=(6, 2))
    make_label(tbl_hdr, "Exam Scores", 12, bold=True, color=MUTED).pack(anchor="w")

    style_treeview()
    tbl_frame = tk.Frame(top, bg=BG)
    tbl_frame.pack(fill="both", expand=True, padx=20, pady=(0, 6))

    cols   = ("course_code", "course_title", "points", "letter", "gpa")
    heads  = ("Course Code", "Course Title", "Points (/ 100)", "Letter", "GPA")
    widths = (110, 220, 130, 80, 80)

    tree = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                        style="D.Treeview", height=7, selectmode="browse")
    for col, head, w in zip(cols, heads, widths):
        tree.heading(col, text=head)
        tree.column(col, width=w, anchor="center")

    sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    # ── Navigation bar ────────────────────────────────────────────────────────
    nav = tk.Frame(top, bg=PANEL)
    nav.pack(fill="x")
    tk.Frame(nav, bg=BORDER, height=1).pack(fill="x")

    inner_nav = tk.Frame(nav, bg=PANEL)
    inner_nav.pack(pady=10)

    prev_btn = make_button(inner_nav, "◀  Previous", None,
                           color=OPTION_COLORS[7], width=160, height=46, radius=23)
    prev_btn.pack(side="left", padx=10)

    counter_var = tk.StringVar()
    tk.Label(inner_nav, textvariable=counter_var,
             font=("Segoe UI", 12, "bold"), fg=TEXT, bg=PANEL,
             width=10, anchor="center").pack(side="left", padx=16)

    next_btn = make_button(inner_nav, "Next  ▶", None,
                           color=OPTION_COLORS[7], width=160, height=46, radius=23)
    next_btn.pack(side="left", padx=10)

    make_button(inner_nav, "Close", top.destroy,
                color=SECONDARY, width=110, height=46, radius=23).pack(side="left", padx=20)

    # ── Show student ──────────────────────────────────────────────────────────
    def show_student(idx):
        current_idx[0] = idx
        sid  = student_ids[idx]
        recs = student_dict[sid]
        first = recs[0]

        id_var.set(f"  {first['student_id']}")
        name_var.set(f"  {first['name']}")
        major_var.set(f"  {first['major']}")

        tree.delete(*tree.get_children())
        for r in recs:
            try:
                letter, _ = points_to_grade(float(r["points"]))
            except (ValueError, TypeError):
                letter = "—"
            tree.insert("", "end", values=(
                r["course_code"], r["course_title"],
                r["points"], letter, r["gpa"],
            ))

        counter_var.set(f"{idx + 1}  /  {total}")

        # Re-wire prev/next with updated index
        prev_btn.bind("<Button-1>",
                      lambda e: show_student(current_idx[0] - 1)
                      if current_idx[0] > 0 else None)
        next_btn.bind("<Button-1>",
                      lambda e: show_student(current_idx[0] + 1)
                      if current_idx[0] < total - 1 else None)

        # Dim buttons at boundaries
        _dim_nav()

    def _dim_nav():
        idx = current_idx[0]
        _set_btn_alpha(prev_btn, active=(idx > 0))
        _set_btn_alpha(next_btn, active=(idx < total - 1))

    def _set_btn_alpha(btn_canvas, active):
        color = OPTION_COLORS[7] if active else SECONDARY
        btn_canvas.delete("all")
        w = int(btn_canvas.cget("width"))
        h = int(btn_canvas.cget("height"))
        r = 23
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        for start, extent in [(90, 90), (0, 90), (180, 90), (270, 90)]:
            bx = x1 if start in (90, 180) else x2 - 2 * r
            by = y1 if start in (0, 90) else y2 - 2 * r
            btn_canvas.create_arc(bx, by, bx + 2*r, by + 2*r,
                                  start=start, extent=extent, fill=color, outline=color)
        btn_canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=color, outline=color)
        btn_canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=color, outline=color)
        text = btn_canvas.itemcget(tk.ALL, "text") if btn_canvas.find_all() else ""
        label = "◀  Previous" if btn_canvas is prev_btn else "Next  ▶"
        btn_canvas.create_text(w // 2, h // 2, text=label,
                               fill="white" if active else MUTED,
                               font=("Segoe UI", 13, "bold"))

    show_student(0)


# =============================================================================
#  Option 8: Student ID Card  (Vanderbilt style)
# =============================================================================

def opt_student_id_card():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    # ── group by student_id ───────────────────────────────────────────────────
    student_dict = {}
    for r in records:
        sid = r["student_id"]
        if sid not in student_dict:
            student_dict[sid] = []
        student_dict[sid].append(r)

    student_ids = list(student_dict.keys())
    total       = len(student_ids)
    current     = [0]

    VU_GOLD  = "#CFAE70"
    VU_BLACK = "#121212"
    CARD_W   = 520
    CARD_H   = 295

    # ── cartoon avatar ────────────────────────────────────────────────────────
    def make_avatar(parent, name, size=110):
        import math
        seed = int(hashlib.md5(name.encode()).hexdigest(), 16)
        SKIN  = ["#FDBCB4","#F1C27D","#E0AC69","#C68642","#8D5524"]
        HAIR  = ["#1a1a1a","#4a3728","#8B4513","#DAA520","#C0392B","#2C1810","#6C3483"]
        SHIRT = [ACCENT, TEAL, "#1d4ed8", GREEN, SECONDARY]
        IRIS  = ["#3b4a6b","#1a7a4a","#7a4a1a","#1a4a7a","#555555"]
        skin   = SKIN [(seed)       % len(SKIN)]
        hair   = HAIR [(seed >>  8) % len(HAIR)]
        shirt  = SHIRT[(seed >> 16) % len(SHIRT)]
        iris   = IRIS [(seed >> 20) % len(IRIS)]
        hstyle = (seed >> 12) % 3
        glasses  = ((seed >> 24) % 4) == 0
        freckles = ((seed >> 28) % 5) == 0
        cv = tk.Canvas(parent, width=size, height=size,
                       bg=VU_BLACK, highlightthickness=0)
        cx = size // 2
        cv.create_oval(2, 2, size-2, size-2, fill="#1a2233", outline=VU_GOLD, width=2)
        by_ = int(size*.70)
        cv.create_arc(int(size*.04), by_-int(size*.32), int(size*.96), size+int(size*.14),
                      start=0, extent=180, fill=shirt, outline="")
        cv.create_polygon(cx-int(size*.07), by_, cx, by_+int(size*.06),
                          cx+int(size*.07), by_, cx+int(size*.04), by_-int(size*.03),
                          cx-int(size*.04), by_-int(size*.03), fill="white", outline="")
        nw = int(size*.08)
        cv.create_rectangle(cx-nw, int(size*.57), cx+nw, by_, fill=skin, outline="")
        hr  = int(size*.265)
        hcx, hcy = cx, int(size*.38)
        if hstyle == 0:
            cv.create_arc(hcx-hr-2, hcy-hr-7, hcx+hr+2, hcy+int(hr*.35),
                          start=0, extent=180, fill=hair, outline="")
        elif hstyle == 1:
            for ang in range(0, 181, 36):
                rad = math.radians(ang)
                bx2 = int(hcx+(hr+9)*math.cos(rad)); by2 = int(hcy-(hr+9)*abs(math.sin(rad)))
                br  = int(hr*.28)
                cv.create_oval(bx2-br, by2-br, bx2+br, by2+br, fill=hair, outline="")
            cv.create_arc(hcx-hr, hcy-hr, hcx+hr, hcy+4, start=0, extent=180,
                          fill=hair, outline="")
        else:
            cv.create_oval(hcx-hr-6, hcy-hr-4, hcx+hr+6, hcy+hr+16, fill=hair, outline="")
        cv.create_oval(hcx-hr, hcy-hr, hcx+hr, hcy+hr, fill=skin, outline="")
        ew, eh = int(hr*.22), int(hr*.28)
        for ex in [hcx-hr, hcx+hr]:
            cv.create_oval(ex-ew, hcy-eh, ex+ew, hcy+eh, fill=skin, outline="")
        ey = hcy-int(hr*.10); exo = int(hr*.36); er = int(hr*.18)
        for ex in [hcx-exo, hcx+exo]:
            cv.create_oval(ex-er, ey-er, ex+er, ey+er, fill="white", outline="#ddd")
            ir_ = int(er*.62)
            cv.create_oval(ex-ir_, ey-ir_, ex+ir_, ey+ir_, fill=iris, outline="")
            pr = int(ir_*.55)
            cv.create_oval(ex-pr, ey-pr, ex+pr, ey+pr, fill="#111", outline="")
            cv.create_oval(ex+pr//3, ey-pr//2, ex+pr//3+2, ey-pr//2+2,
                           fill="white", outline="")
        for ex in [hcx-exo, hcx+exo]:
            sl = 2 if ex < hcx else -2
            cv.create_line(ex-er, ey-er-4+sl, ex+er, ey-er-4-sl,
                           fill=hair, width=2, capstyle="round")
        ny = hcy+int(hr*.20)
        nc = "#c8906a" if skin in SKIN[:3] else "#7a5540"
        cv.create_oval(hcx-4, ny, hcx-1, ny+5, fill=nc, outline="")
        cv.create_oval(hcx+1, ny, hcx+4, ny+5, fill=nc, outline="")
        my_ = hcy+int(hr*.46); mw = int(hr*.44)
        cv.create_arc(hcx-mw, my_-mw//2, hcx+mw, my_+mw//2,
                      start=200, extent=140, outline="#b03a2e", style="arc", width=2)
        cv.create_arc(hcx-mw+3, my_-mw//2+2, hcx+mw-3, my_+mw//2,
                      start=200, extent=140, fill="white", outline="", style="chord")
        if freckles:
            for fx, fy in [(hcx-14,hcy+6),(hcx-10,hcy+10),(hcx+10,hcy+6),(hcx+14,hcy+10)]:
                cv.create_oval(fx-2, fy-2, fx+2, fy+2, fill="#c8906a", outline="")
        if glasses:
            gr = int(er*1.55)
            for ex in [hcx-exo, hcx+exo]:
                cv.create_oval(ex-gr, ey-gr, ex+gr, ey+gr, fill="", outline="#999", width=2)
            cv.create_line(hcx-exo+gr, ey, hcx+exo-gr, ey, fill="#999", width=2)
        return cv

    # ── barcode ───────────────────────────────────────────────────────────────
    def make_barcode(parent, seed_str, w=CARD_W, h=34):
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) & 0xFFFFFFFF
        rng  = np.random.default_rng(seed)
        cv   = tk.Canvas(parent, width=w, height=h, bg=VU_GOLD, highlightthickness=0)
        x = 10
        while x < w - 10:
            bw = int(rng.choice([1, 1, 2, 2, 3]))
            gp = int(rng.choice([1, 2, 3]))
            cv.create_rectangle(x, 3, x+bw, h-8, fill=VU_BLACK, outline="")
            x += bw + gp
        cv.create_text(w//2, h-3, text=seed_str, anchor="s",
                       fill=VU_BLACK, font=("Courier New", 7, "bold"))
        return cv

    # ── populate_card: clear and refill the fixed card frame ─────────────────
    def populate_card(card_body, sid):
        for w in card_body.winfo_children():
            w.destroy()
        first = student_dict[sid][0]
        recs  = student_dict[sid]

        # gold header bar
        hdr = tk.Frame(card_body, bg=VU_GOLD, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="V",
                 font=("Georgia", 36, "bold"), fg=VU_BLACK, bg=VU_GOLD).pack(
                     side="left", padx=(12, 2), pady=2)
        hi = tk.Frame(hdr, bg=VU_GOLD)
        hi.pack(side="left", pady=6)
        tk.Label(hi, text="VANDERBILT UNIVERSITY",
                 font=("Georgia", 13, "bold"), fg=VU_BLACK, bg=VU_GOLD).pack(anchor="w")
        tk.Label(hi, text="Student Identification Card",
                 font=("Segoe UI", 8), fg="#4a3800", bg=VU_GOLD).pack(anchor="w")
        tk.Label(hdr, text="2026",
                 font=("Segoe UI", 10, "bold"), fg=VU_BLACK, bg=VU_GOLD).pack(
                     side="right", padx=12)

        # body area
        body = tk.Frame(card_body, bg=VU_BLACK)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # left: avatar + "STUDENT" label
        left = tk.Frame(body, bg=VU_BLACK)
        left.pack(side="left", padx=(0, 12))
        make_avatar(left, first["name"]).pack()
        tk.Label(left, text="S T U D E N T",
                 font=("Segoe UI", 7, "bold"), fg=VU_GOLD, bg=VU_BLACK).pack(pady=(4, 0))

        # gold vertical divider
        tk.Frame(body, bg=VU_GOLD, width=2).pack(side="left", fill="y", padx=(0, 12))

        # right: student info
        right = tk.Frame(body, bg=VU_BLACK)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text=first["name"],
                 font=("Georgia", 16, "bold"), fg="white", bg=VU_BLACK,
                 wraplength=250, justify="left").pack(anchor="w")
        tk.Label(right, text=first["major"],
                 font=("Segoe UI", 11), fg=VU_GOLD, bg=VU_BLACK).pack(anchor="w", pady=(3, 0))
        tk.Label(right, text="Vanderbilt University  ·  Nashville, TN",
                 font=("Segoe UI", 8), fg="#666666", bg=VU_BLACK).pack(anchor="w", pady=(2, 6))
        tk.Frame(right, bg=VU_GOLD, height=1).pack(fill="x", pady=(0, 6))
        tk.Label(right, text="STUDENT ID",
                 font=("Segoe UI", 7, "bold"), fg="#777777", bg=VU_BLACK).pack(anchor="w")
        tk.Label(right, text=first["student_id"],
                 font=("Courier New", 15, "bold"), fg=VU_GOLD, bg=VU_BLACK).pack(anchor="w")
        tk.Label(right, text=f"Enrolled courses: {len(recs)}",
                 font=("Segoe UI", 8), fg="#666666", bg=VU_BLACK).pack(anchor="w", pady=(6, 0))

        # barcode footer
        make_barcode(card_body, first["student_id"]).pack(fill="x")

    # ── popup window ──────────────────────────────────────────────────────────
    top = tk.Toplevel(root)
    top.title("Vanderbilt Student ID Card")
    top.configure(bg=BG)
    top.resizable(False, False)
    top.grab_set()
    top.geometry("780x600")

    # accent bar
    tk.Frame(top, bg=OPTION_COLORS[8], height=5).pack(fill="x")

    # title + search
    topbar = tk.Frame(top, bg=PANEL)
    topbar.pack(fill="x")
    tk.Frame(topbar, bg=OPTION_COLORS[8], height=2).pack(fill="x")
    make_label(topbar, "Student ID Card", 15, bold=True).pack(
        side="left", padx=18, pady=10)
    srch_row = tk.Frame(topbar, bg=PANEL)
    srch_row.pack(side="right", padx=18, pady=8)
    make_label(srch_row, "Search ID:", 11, color=MUTED).pack(side="left", padx=(0, 6))
    sw = tk.Frame(srch_row, bg=CYAN, padx=1, pady=1)
    sw.pack(side="left")
    srch_e = tk.Entry(sw, font=("Segoe UI", 11), bg=CARD, fg=TEXT,
                      insertbackground=CYAN, relief="flat", width=13)
    srch_e.pack()

    def do_search():
        sid = srch_e.get().strip()
        if not sid:
            return
        if sid in student_dict:
            show_card(student_ids.index(sid))
        else:
            messagebox.showwarning("Not Found",
                                   f"Student ID '{sid}' not found.", parent=top)

    make_button(srch_row, "Search", do_search,
                color=OPTION_COLORS[8], width=100, height=36, radius=18).pack(
                    side="left", padx=(8, 0))
    srch_e.bind("<Return>", lambda _: do_search())

    # ── permanent gold-bordered card frame (created once, never destroyed) ────
    card_outer = tk.Frame(top, bg=VU_GOLD)
    card_outer.pack(pady=24)                      # centers horizontally by default

    card_body = tk.Frame(card_outer, bg=VU_BLACK, width=CARD_W, height=CARD_H)
    card_body.pack(padx=3, pady=3)
    card_body.pack_propagate(False)               # keeps exact CARD_W × CARD_H

    # ── nav bar ───────────────────────────────────────────────────────────────
    tk.Frame(top, bg=BORDER, height=1).pack(fill="x")
    nav = tk.Frame(top, bg=PANEL)
    nav.pack(fill="x")
    inner_nav = tk.Frame(nav, bg=PANEL)
    inner_nav.pack(pady=18)

    counter_var = tk.StringVar(value="")

    # NOTE: plain tk.Button ignores bg/activebackground on macOS (Aqua theme
    # renders buttons natively and refuses to recolor them), so we use a
    # ttk.Button on the "clam" theme instead — that theme paints its own
    # button face and actually honors the colors we set below.
    nav_style = ttk.Style()
    nav_style.theme_use("clam")
    nav_style.configure("Nav.TButton",
                        font=("Segoe UI", 12, "bold"),
                        background="#121212", foreground="white",
                        bordercolor="#121212", focuscolor="#121212",
                        padding=(22, 11), relief="flat")
    nav_style.map("Nav.TButton",
                  background=[("disabled", SECONDARY),
                              ("active", "#2a2a2a")],
                  foreground=[("disabled", "#8a8a8a"),
                              ("active", "white")])

    prev_btn = ttk.Button(inner_nav, text="◀  Previous", style="Nav.TButton",
                          cursor="hand2",
                          command=lambda: show_card(current[0] - 1))
    prev_btn.pack(side="left", padx=12)

    tk.Label(inner_nav, textvariable=counter_var,
             font=("Segoe UI", 13, "bold"), fg=TEXT, bg=PANEL,
             width=10, anchor="center").pack(side="left", padx=16)

    next_btn = ttk.Button(inner_nav, text="Next  ▶", style="Nav.TButton",
                          cursor="hand2",
                          command=lambda: show_card(current[0] + 1))
    next_btn.pack(side="left", padx=12)

    make_button(inner_nav, "Close", top.destroy,
                color=SECONDARY, width=140, height=48, radius=24).pack(
                    side="left", padx=20)

    # ── show_card: just repopulate the fixed frame ────────────────────────────
    def show_card(i):
        current[0] = i
        populate_card(card_body, student_ids[i])
        counter_var.set(f"{i + 1}  /  {total}")
        prev_btn.config(state="normal" if i > 0       else "disabled")
        next_btn.config(state="normal" if i < total-1 else "disabled")

    show_card(0)   # first student shown by default


# =============================================================================
#  Option 9: Queries
# =============================================================================

def opt_queries():
    records = load_students()
    if not records:
        messagebox.showwarning("No Data",
                               "No student records found.\nAdd students first using Option 0.",
                               parent=root)
        return

    student_dict = {}
    for r in records:
        student_dict.setdefault(r["student_id"], []).append(r)

    def grade_letter(r):
        try:
            letter, _ = points_to_grade(float(r["points"]))
            return letter
        except (ValueError, TypeError):
            return None

    def distinct_students(pred):
        return len({r["student_id"] for r in records if pred(r)})

    def avg_points(pred):
        vals = [float(r["points"]) for r in records if pred(r)]
        return sum(vals) / len(vals) if vals else None

    def avg_gpa(pred):
        vals = [float(r["gpa"]) for r in records if pred(r)]
        return sum(vals) / len(vals) if vals else None

    def plural(n, word="student"):
        return f"{n} {word}{'s' if n != 1 else ''}"

    # ── Q1 — CS students who earned an A+ ─────────────────────────────────────
    q1 = distinct_students(lambda r: r["major"] == "Computer Science"
                                      and grade_letter(r) == "A+")

    # ── Q2 — Mechanical Engineering students who took a CS/programming course ─
    q2 = distinct_students(lambda r: r["major"] == "Mechanical Engineering"
                                      and "program" in r["course_title"].lower())

    # ── Q3 — students (any major) who took a programming class ────────────────
    q3 = distinct_students(lambda r: "program" in r["course_title"].lower())

    # ── Q4 — average GPA of Computer Science majors ───────────────────────────
    v4 = avg_gpa(lambda r: r["major"] == "Computer Science")
    q4 = f"{v4:.2f} GPA" if v4 is not None else "No data"

    # ── Q5 — major with the highest average GPA ───────────────────────────────
    majors = sorted({r["major"] for r in records})
    major_gpa = {m: avg_gpa(lambda r, m=m: r["major"] == m) for m in majors}
    major_gpa = {m: v for m, v in major_gpa.items() if v is not None}
    if major_gpa:
        top_major = max(major_gpa, key=major_gpa.get)
        q5 = f"{top_major}  ({major_gpa[top_major]:.2f} avg GPA)"
    else:
        q5 = "No data"

    # ── Q6 — students who failed (grade F) in Circuit Analysis ────────────────
    q6 = distinct_students(lambda r: r["course_title"] == "Circuit Analysis"
                                      and grade_letter(r) == "F")

    # ── Q7 — total unique students enrolled ────────────────────────────────────
    q7 = len(student_dict)

    # ── Q8 — average score in Calculus I ───────────────────────────────────────
    v8 = avg_points(lambda r: r["course_title"] == "Calculus I")
    q8 = f"{v8:.1f} / 100" if v8 is not None else "No data"

    # ── Q9 — students who scored 90+ in Introduction to Business ──────────────
    q9 = distinct_students(lambda r: r["course_title"] == "Introduction to Business"
                                      and float(r["points"]) >= 90)

    # ── Q10 — course with the lowest average score overall ────────────────────
    titles = sorted({r["course_title"] for r in records})
    title_pts = {t: avg_points(lambda r, t=t: r["course_title"] == t) for t in titles}
    title_pts = {t: v for t, v in title_pts.items() if v is not None}
    if title_pts:
        low_title = min(title_pts, key=title_pts.get)
        q10 = f"{low_title}  ({title_pts[low_title]:.1f} avg pts)"
    else:
        q10 = "No data"

    QUERIES = [
        ("How many students from Computer Science earned an A+?",
         plural(q1)),
        ("How many students from Mechanical Engineering took a programming (CS) course?",
         plural(q2)),
        ("How many students, across all majors, took a programming class?",
         plural(q3)),
        ("What is the average GPA of Computer Science majors?",
         q4),
        ("Which major has the highest average GPA?",
         q5),
        ("How many students earned an F in Circuit Analysis?",
         plural(q6)),
        ("How many unique students are enrolled in total?",
         plural(q7)),
        ("What is the average score in Calculus I?",
         q8),
        ("How many students scored 90 or above in Introduction to Business?",
         plural(q9)),
        ("Which course has the lowest average score overall?",
         q10),
    ]

    # ── popup window ──────────────────────────────────────────────────────────
    top = make_popup("Queries — Academic Insights", w=820, h=700, resizable=True)
    tk.Frame(top, bg=OPTION_COLORS[9], height=5).pack(fill="x")

    hdr = tk.Frame(top, bg=PANEL)
    hdr.pack(fill="x")
    tk.Frame(hdr, bg=OPTION_COLORS[9], height=2).pack(fill="x")
    make_label(hdr, "Queries — Academic Insights", 15, bold=True).pack(
        anchor="w", padx=18, pady=(10, 0))
    make_label(hdr, f"Computed live from {len(records)} enrollment record(s)  ·  "
                     f"{len(student_dict)} student(s)",
               10, color=MUTED).pack(anchor="w", padx=18, pady=(2, 10))

    # ── scrollable list of Q/A cards ────────────────────────────────────────────
    container = tk.Frame(top, bg=BG)
    container.pack(fill="both", expand=True, padx=16, pady=(10, 0))

    canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
    sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=BG)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)

    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    for i, (question, answer) in enumerate(QUERIES, start=1):
        card = tk.Frame(scroll_frame, bg=CARD)
        card.pack(fill="x", pady=6, padx=2)

        accent = tk.Frame(card, bg=OPTION_COLORS[9], width=4)
        accent.pack(side="left", fill="y")

        body = tk.Frame(card, bg=CARD, padx=14, pady=10)
        body.pack(side="left", fill="both", expand=True)

        make_label(body, f"Q{i}.  {question}", 11, bold=True,
                   color=TEXT, wraplength=680, justify="left").pack(anchor="w")
        tk.Label(body, text=f"→   {answer}", font=("Segoe UI", 12, "bold"),
                 fg=CYAN, bg=CARD, wraplength=680, justify="left").pack(
                     anchor="w", pady=(4, 0))

    footer_close_btn(top, top.destroy, label="✕  Close")


# =============================================================================
#  Entry point
# =============================================================================

def main():
    global root
    load_gpa_scale()
    root = tk.Tk()
    root.title("FEST Summer 2026")
    root.configure(bg=BG)
    # Full-screen: fill the entire screen
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")
    root.resizable(True, True)
    show_welcome()
    root.update_idletasks()
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.after(250, lambda: root.attributes("-topmost", False))
    root.after(300, root.focus_force)
    root.mainloop()


if __name__ == "__main__":
    main()
