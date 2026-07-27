# PART 1: Your First Tkinter Window
import tkinter as tk

root = tk.Tk()                       # create the main window (like main.py's root = tk.Tk())
root.title("FEST Student Manager")   # window title bar text
root.geometry("400x200")             # width x height in pixels

label = tk.Label(root, text="Welcome to FEST 2026", font=("Segoe UI", 14))
label.pack(pady=40)                  # place the label in the window

root.mainloop()                      # start the event loop (shows the window)