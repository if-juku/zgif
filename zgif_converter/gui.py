"""Small desktop interface. All Tk operations stay on the UI thread."""

from pathlib import Path
import queue
import threading
import sys

from .converter import Options, convert


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("画面の起動にはTkが必要です。Ubuntu: sudo apt install python3-tk", file=sys.stderr)
        return 1

    window = tk.Tk()
    window.title("ZGIF Converter — 動くスタンプを作る")
    window.geometry("720x610")
    window.minsize(640, 580)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="ZGIF Converter", font=("", 22, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    ttk.Label(frame, text="動画から、チャットで使う動くスタンプへ。MP4 / MOV / WebM など").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))
    values = {key: tk.StringVar(value=value) for key, value in {
        "source": "", "output": "", "width": "512", "height": "512", "fps": "15",
        "quality": "3", "start": "0", "duration": "", "key_color": "#00ff00",
    }.items()}
    controls = []
    busy = False

    def pick_source():
        path = filedialog.askopenfilename(title="動画を選択", filetypes=[
            ("動画", "*.mp4 *.mov *.webm *.mkv *.avi *.m4v *.gif"), ("すべて", "*")])
        if path:
            values["source"].set(path)
            values["output"].set(str(Path(path).with_suffix(".zgif")))

    def pick_output():
        path = filedialog.asksaveasfilename(title="ZGIFの保存先", defaultextension=".zgif",
                                          filetypes=[("ZGIF", "*.zgif")])
        if path:
            values["output"].set(path)

    labels = [("source", "入力動画"), ("output", "保存先"), ("width", "幅（px）"),
              ("height", "高さ（px）"), ("fps", "FPS"), ("quality", "JPEG品質（2〜31）"),
              ("start", "開始秒"), ("duration", "長さ（秒・空欄で最後まで）"),
              ("key_color", "透過色 / 余白色（RGB）")]
    for row, (key, label) in enumerate(labels, 2):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=5)
        entry = ttk.Entry(frame, textvariable=values[key])
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        controls.append(entry)
        if key in ("source", "output"):
            button = ttk.Button(frame, text="選択…", command=pick_source if key == "source" else pick_output)
            button.grid(row=row, column=2, padx=(8, 0))
            controls.append(button)
    ttk.Label(frame, text="縦横比を保ち、余白を透過色で埋めます。音声は入りません。\n"
              "透過色と同じ色の被写体も透けます。背景の自動切り抜きは行いません。\n"
              "JPEG品質は小さい値ほど高画質です。", wraplength=630).grid(
                  row=11, column=0, columnspan=3, sticky="w", pady=(12, 12))
    message = tk.StringVar(value="動画と保存先を選んでください。")
    events = queue.Queue()

    def run_conversion(source, output, options, overwrite):
        try:
            convert(source, output, options, overwrite=overwrite,
                    status=lambda text: events.put(("status", text)))
            events.put(("done", output))
        except Exception as exc:
            events.put(("error", str(exc)))

    def start():
        nonlocal busy
        if not values["source"].get().strip() or not values["output"].get().strip():
            messagebox.showerror("入力を確認", "入力動画と保存先を指定してください。")
            return
        try:
            options = Options(
                width=int(values["width"].get()), height=int(values["height"].get()),
                fps=int(values["fps"].get()), quality=int(values["quality"].get()),
                start=float(values["start"].get()),
                duration=float(values["duration"].get()) if values["duration"].get().strip() else None,
                key_color=values["key_color"].get().strip())
            options.validate()
        except ValueError:
            messagebox.showerror("入力を確認", "幅・高さ・FPS・品質は整数、開始秒・長さは数値で指定してください。")
            return
        except Exception as exc:
            messagebox.showerror("入力を確認", str(exc))
            return
        output = values["output"].get().strip()
        overwrite = Path(output).expanduser().exists()
        if overwrite and not messagebox.askyesno("上書き確認", f"既存のファイルを上書きしますか？\n{output}"):
            return
        busy = True
        for control in controls:
            control.configure(state="disabled")
        progress.start()
        message.set("変換を開始しています…")
        threading.Thread(target=run_conversion,
                         args=(values["source"].get().strip(), output, options, overwrite), daemon=True).start()

    button = ttk.Button(frame, text="ZGIFに変換", command=start)
    button.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(0, 12))
    controls.append(button)
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.grid(row=13, column=0, columnspan=3, sticky="ew")
    ttk.Label(frame, textvariable=message, wraplength=630).grid(
        row=14, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def poll():
        nonlocal busy
        try:
            while True:
                kind, text = events.get_nowait()
                if kind == "status":
                    message.set(text)
                else:
                    busy = False
                    progress.stop()
                    for control in controls:
                        control.configure(state="normal")
                    if kind == "done":
                        message.set(f"保存しました: {text}")
                        messagebox.showinfo("変換完了", f"ZGIFを保存しました。\n{text}")
                    else:
                        message.set("変換に失敗しました。設定と入力動画を確認してください。")
                        messagebox.showerror("変換エラー", text)
        except queue.Empty:
            pass
        window.after(100, poll)

    def close():
        if busy:
            messagebox.showinfo("変換中", "変換が終わってから画面を閉じてください。")
        else:
            window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.after(100, poll)
    window.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
