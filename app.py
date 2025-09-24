"""Interactive GUI tool to help backend developers test HTTP endpoints."""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText


REQUEST_TIMEOUT = 60


@dataclass
class RequestHistoryItem:
    method: str
    url: str
    headers: Dict[str, str]
    body: str
    response_status: Optional[int] = None
    response_time: Optional[float] = None
    response_preview: str = ""

    def display_label(self) -> str:
        status = self.response_status if self.response_status is not None else "..."
        duration = (
            f"{self.response_time * 1000:.0f} ms"
            if self.response_time is not None
            else "pending"
        )
        return f"{self.method} {self.url} ({status}, {duration})"


class ApiTesterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Backend Dev Helper")
        self.root.geometry("1100x720")

        self.request_queue: "queue.Queue[RequestHistoryItem]" = queue.Queue()
        self.response_queue: "queue.Queue[RequestHistoryItem]" = queue.Queue()
        self.history: List[RequestHistoryItem] = []

        self._build_layout()
        self._start_response_loop()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = tk.Frame(self.root)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(1, weight=1)

        # History panel
        history_frame = tk.LabelFrame(main, text="History")
        history_frame.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=5, pady=5)
        history_frame.rowconfigure(0, weight=1)
        history_frame.columnconfigure(0, weight=1)

        self.history_listbox = tk.Listbox(history_frame, height=10)
        self.history_listbox.grid(row=0, column=0, sticky="nsew")
        self.history_listbox.bind("<<ListboxSelect>>", self._load_history_item)

        history_buttons = tk.Frame(history_frame)
        history_buttons.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        tk.Button(history_buttons, text="Load", command=self._load_selected_history).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(history_buttons, text="Delete", command=self._delete_selected_history).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(history_buttons, text="Clear", command=self._clear_history).pack(
            side=tk.LEFT, padx=2
        )

        # Request form
        request_frame = tk.LabelFrame(main, text="Request")
        request_frame.grid(row=0, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        for col, weight in enumerate((0, 1, 1, 0)):
            request_frame.columnconfigure(col, weight=weight)

        tk.Label(request_frame, text="Method:").grid(row=0, column=0, sticky="w", padx=2)
        self.method_var = tk.StringVar(value="GET")
        method_menu = tk.OptionMenu(
            request_frame,
            self.method_var,
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "HEAD",
            "OPTIONS",
        )
        method_menu.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        tk.Label(request_frame, text="URL:").grid(row=0, column=2, sticky="w", padx=2)
        self.url_entry = tk.Entry(request_frame)
        self.url_entry.grid(row=0, column=3, sticky="ew", padx=2, pady=2)

        tk.Label(request_frame, text="Headers (key: value per line):").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=2
        )
        self.headers_text = ScrolledText(request_frame, height=6)
        self.headers_text.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)

        tk.Label(request_frame, text="Body:").grid(row=1, column=2, sticky="w", padx=2)
        self.body_text = ScrolledText(request_frame, height=6)
        self.body_text.grid(row=2, column=2, columnspan=2, sticky="nsew", padx=2, pady=2)

        tk.Button(
            request_frame,
            text="Send",
            command=self._queue_request,
            bg="#136f63",
            fg="white",
            activebackground="#1a947f",
        ).grid(row=3, column=3, sticky="e", padx=5, pady=5)

        # Response panel
        response_frame = tk.LabelFrame(main, text="Response")
        response_frame.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        response_frame.columnconfigure(0, weight=1)
        response_frame.rowconfigure(2, weight=1)

        tk.Label(response_frame, text="Status:").grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="-")
        tk.Label(response_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="e", padx=60)

        tk.Label(response_frame, text="Elapsed:").grid(row=1, column=0, sticky="w")
        self.elapsed_var = tk.StringVar(value="-")
        tk.Label(response_frame, textvariable=self.elapsed_var).grid(row=1, column=0, sticky="e", padx=60)

        tk.Label(response_frame, text="Headers:").grid(row=2, column=0, sticky="w")
        self.response_headers_text = ScrolledText(response_frame, height=8)
        self.response_headers_text.grid(row=3, column=0, sticky="nsew", padx=2, pady=2)

        tk.Label(response_frame, text="Body:").grid(row=4, column=0, sticky="w")
        self.response_body_text = ScrolledText(response_frame, height=12)
        self.response_body_text.grid(row=5, column=0, sticky="nsew", padx=2, pady=2)

        # Tips panel
        tips_frame = tk.LabelFrame(main, text="Tips")
        tips_frame.grid(row=2, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        tips_frame.columnconfigure(0, weight=1)
        tips_text = (
            "• Use ⌘+Enter / Ctrl+Enter in the body field to send the request quickly.\n"
            "• Provide multiple headers as `Header: Value` per line.\n"
            "• When the response looks like JSON, it will be automatically formatted."
        )
        tk.Label(tips_frame, text=tips_text, justify=tk.LEFT, anchor="w").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )

        self.body_text.bind("<Control-Return>", lambda event: self._queue_request())
        self.body_text.bind("<Command-Return>", lambda event: self._queue_request())

    def _queue_request(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Missing URL", "Please provide a URL before sending.")
            return
        method = self.method_var.get().upper()
        headers = self._parse_headers(self.headers_text.get("1.0", tk.END))
        body = self.body_text.get("1.0", tk.END).strip()

        item = RequestHistoryItem(method=method, url=url, headers=headers, body=body)
        self.history.append(item)
        self._refresh_history_listbox()
        self.request_queue.put(item)
        self.status_var.set("Pending...")
        self.elapsed_var.set("-")
        self.response_headers_text.delete("1.0", tk.END)
        self.response_body_text.delete("1.0", tk.END)

        if self.request_queue.qsize() == 1:
            threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self) -> None:
        while not self.request_queue.empty():
            item = self.request_queue.get()
            start = time.perf_counter()
            try:
                response = requests.request(
                    method=item.method,
                    url=item.url,
                    headers=item.headers or None,
                    data=item.body or None,
                    timeout=REQUEST_TIMEOUT,
                )
                elapsed = time.perf_counter() - start
                preview = response.text[:200].replace("\n", " ")
                item.response_status = response.status_code
                item.response_time = elapsed
                item.response_preview = preview
                result = {
                    "status": f"{response.status_code} {response.reason}",
                    "elapsed": f"{elapsed:.2f} s",
                    "headers": json.dumps(dict(response.headers), indent=2),
                    "body": self._format_body(response.text),
                }
            except requests.exceptions.RequestException as exc:
                elapsed = time.perf_counter() - start
                item.response_status = None
                item.response_time = elapsed
                item.response_preview = str(exc)
                result = {
                    "status": "Request failed",
                    "elapsed": f"{elapsed:.2f} s",
                    "headers": "",
                    "body": str(exc),
                }
            self.response_queue.put((item, result))

    def _start_response_loop(self) -> None:
        def poll_queue() -> None:
            try:
                while True:
                    item, result = self.response_queue.get_nowait()
                    if item == self.history[-1]:
                        self._display_response(result)
                    self._refresh_history_listbox()
            except queue.Empty:
                pass
            finally:
                self.root.after(150, poll_queue)

        poll_queue()

    def _display_response(self, result: Dict[str, str]) -> None:
        self.status_var.set(result["status"])
        self.elapsed_var.set(result["elapsed"])
        self.response_headers_text.delete("1.0", tk.END)
        self.response_headers_text.insert("1.0", result["headers"])
        self.response_body_text.delete("1.0", tk.END)
        self.response_body_text.insert("1.0", result["body"])

    def _refresh_history_listbox(self) -> None:
        self.history_listbox.delete(0, tk.END)
        for item in reversed(self.history):
            self.history_listbox.insert(tk.END, item.display_label())

    def _load_history_item(self, event: tk.Event[tk.Listbox]) -> None:  # type: ignore[name-defined]
        if not self.history:
            return
        selection = self.history_listbox.curselection()
        if not selection:
            return
        index = len(self.history) - 1 - selection[0]
        self._populate_form(self.history[index])

    def _load_selected_history(self) -> None:
        selection = self.history_listbox.curselection()
        if selection:
            index = len(self.history) - 1 - selection[0]
            self._populate_form(self.history[index])

    def _delete_selected_history(self) -> None:
        selection = self.history_listbox.curselection()
        if not selection:
            return
        index = len(self.history) - 1 - selection[0]
        del self.history[index]
        self._refresh_history_listbox()

    def _clear_history(self) -> None:
        if messagebox.askyesno("Clear history", "Remove all saved requests?"):
            self.history.clear()
            self._refresh_history_listbox()

    def _populate_form(self, item: RequestHistoryItem) -> None:
        self.method_var.set(item.method)
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, item.url)
        self.headers_text.delete("1.0", tk.END)
        headers_lines = [f"{k}: {v}" for k, v in item.headers.items()]
        self.headers_text.insert("1.0", "\n".join(headers_lines))
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert("1.0", item.body)

    @staticmethod
    def _parse_headers(raw: str) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for line in raw.strip().splitlines():
            if not line.strip():
                continue
            if ":" not in line:
                messagebox.showwarning(
                    "Invalid header",
                    f"Header '{line}' is missing a colon. It will be ignored.",
                )
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers

    @staticmethod
    def _format_body(body: str) -> str:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return body
        return json.dumps(parsed, indent=2)


def main() -> None:
    root = tk.Tk()
    app = ApiTesterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
