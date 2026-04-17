from __future__ import annotations

import sys


def main() -> None:
    try:
        from voice_bot.gui import main as start_app
    except ModuleNotFoundError as exc:
        package = exc.name or "dependencia"
        message = (
            f"Dependencia ausente: {package}\n\n"
            "Instale os pacotes com:\n"
            "python -m pip install -r requirements.txt"
        )
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Discord Voice TTS Bot", message)
            root.destroy()
        except Exception:
            print(message, file=sys.stderr)
        raise SystemExit(1) from exc

    start_app()


if __name__ == "__main__":
    main()
