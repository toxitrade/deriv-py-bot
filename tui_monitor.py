#!/usr/bin/env python3
"""
TUI Monitor simple para Deriv Bot - estilo wavemon
Ejecución: python tui_monitor.py
"""

from typing import Optional
import httpx
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable

API_BASE = "https://deriv-py-bot.onrender.com"
REFRESH_INTERVAL = 5


class DerivTUI(App):
    CSS = """
    Screen { background: #0b0f14; }
    Header { background: #111827; color: #e5e7eb; border: solid #1f2937; border-top: none; border-left: none; border-right: none; }
    Footer { background: #111827; color: #9ca3af; border: solid #1f2937; border-bottom: none; border-left: none; border-right: none; }
    DataTable { background: #0b0f14; color: #e5e7eb; border: solid #1f2937; height: 1fr; }
    DataTable > .datatable--header { background: #111827; color: #9ca3af; text-style: bold; }
    DataTable > .datatable--cursor { background: #3b82f6; color: #000; }
    """

    BINDINGS = [("q", "quit", "Salir"), ("s", "start", "Start"), ("x", "stop", "Stop"), ("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status")
        yield DataTable(id="trades")
        yield Footer()

    async def on_mount(self):
        import httpx
        self.client = httpx.AsyncClient(timeout=10.0)
        self.set_interval(5, self.fetch_data)
        table = self.query_one("#trades", DataTable)
        table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
        await self.fetch_data()

    async def on_unmount(self):
        if hasattr(self, "client"):
            await self.client.aclose()

    async def fetch_data(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{API_BASE}/status")
                if r.status_code == 200:
                    self.update_ui(r.json())
        except Exception as e:
            self.notify(f"Error: {e}")

    def update_ui(self, s: dict):
        bal = s.get("balance", 0)
        pnl = s.get("daily_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else "-"
        trades_today = s.get("trades_today", 0)
        ticks = s.get("ticks_received", 0)
        price = s.get("last_price", 0)
        hma = s.get("last_hma", 0)
        flow = s.get("last_flow", 0)
        direction = s.get("last_direction", 0)
        mart = s.get("martingale_step", 0)
        symbol = s.get("symbol", "1HZ50V")

        # Top status bar
        self.query_one("#status", Static).update(
            f"Saldo: ${bal:,.2f}  PnL: {'+' if pnl>=0 else '-'}${abs(pnl):,.2f}  Trades: {trades_today}  Ticks: {ticks}  "
            f"Precio: {price:,.4f}  HMA: {hma:,.4f}  Flow: {flow:,.4f}  Dir: {'UP' if direction==1 else 'DOWN' if direction==-1 else 'FLAT'}  Mart: {mart}  Sym: {symbol}"
        )

        # Update trades table
        t = self.query_one("#trades", DataTable)
        t.clear()
        for tr in list(reversed(s.get("trades", [])))[:20]:
            pnl = tr.get("pnl")
            pnl_str = f"+{pnl:.2f}" if pnl and pnl > 0 else f"{pnl:.2f}" if pnl else "--"
            win = tr.get("win")
            result = "WIN" if win is True else "LOSS" if win is False else "OPEN"
            self.query_one("#trades", DataTable).add_row(
                tr.get("entry_time", "--"),
                tr.get("side", "--"),
                f"{tr.get('entry_price', 0):.4f}" if tr.get("entry_price") else "--",
                f"{tr.get('exit_price', 0):.4f}" if tr.get("exit_price") else "--",
                f"{tr.get('stake', 0):.2f}" if tr.get("stake") else "--",
                pnl_str,
                "WIN" if win is True else "LOSS" if win is False else "OPEN"
            )

    async def on_mount(self):
        import httpx
        self.client = httpx.AsyncClient(timeout=10.0)
        self.set_interval(5, self.fetch_data)
        table = self.query_one("#trades", DataTable)
        table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
        await self.fetch_data()

    async def on_unmount(self):
        if hasattr(self, "client"):
            await self.client.aclose()

    async def fetch_data(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{API_BASE}/status")
                if r.status_code == 200:
                    self.update_ui(r.json())
        except Exception as e:
            self.notify(f"Error: {e}")

    async def on_unmount(self):
        if hasattr(self, "client"):
            await self.client.aclose()

    def update_ui(self, s: dict):
        bal = s.get("balance", 0)
        pnl = s.get("daily_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else "-"
        trades_today = s.get("trades_today", 0)
        ticks = s.get("ticks_received", 0)
        price = s.get("last_price", 0)
        hma = s.get("last_hma", 0)
        flow = s.get("last_flow", 0)
        direction = s.get("last_direction", 0)
        mart = s.get("martingale_step", 0)
        symbol = s.get("symbol", "1HZ50V")

        # Top status bar
        self.query_one("#status", Static).update(
            f"Saldo: ${bal:,.2f}  PnL: {'+' if pnl>=0 else '-'}${abs(pnl):,.2f}  Trades: {trades_today}  Ticks: {ticks}  "
            f"Precio: {price:,.4f}  HMA: {hma:,.4f}  Flow: {flow:,.4f}  Dir: {'UP' if direction==1 else 'DOWN' if direction==-1 else 'FLAT'}  Mart: {mart}  Sym: {symbol}"
        )

        t = self.query_one("#trades", DataTable)
        t.clear()
        for tr in list(reversed(s.get("trades", [])))[:20]:
            pnl = tr.get("pnl")
            pnl_str = f"+{pnl:.2f}" if pnl and pnl > 0 else f"{pnl:.2f}" if pnl else "--"
            win = tr.get("win")
            result = "WIN" if win is True else "LOSS" if win is False else "OPEN"
            self.query_one("#trades", DataTable).add_row(
                tr.get("entry_time", "--"),
                tr.get("side", "--"),
                f"{tr.get('entry_price', 0):.4f}" if tr.get("entry_price") else "--",
                f"{tr.get('exit_price', 0):.4f}" if tr.get("exit_price") else "--",
                f"{tr.get('stake', 0):.2f}" if tr.get("stake") else "--",
                pnl_str,
                "WIN" if win is True else "LOSS" if win is False else "OPEN"
            )

    async def on_mount(self):
        import httpx
        self.client = httpx.AsyncClient(timeout=10.0)
        self.set_interval(5, self.fetch_data)
        table = self.query_one("#trades", DataTable)
        table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
        await self.fetch_data()

    async def on_unmount(self):
        if hasattr(self, "client"):
            await self.client.aclose()

    async def fetch_data(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{API_BASE}/status")
                if r.status_code == 200:
                    self.update_ui(r.json())
        except Exception as e:
            self.notify(f"Error: {e}")

    async def on_unmount(self):
        if hasattr(self, "client"):
            await self.client.aclose()


if __name__ == "__main__":
    import httpx
    from textual.app import App
    from textual.widgets import Header, Footer, Static, DataTable

    class DerivTUI(App):
        CSS = """
        Screen { background: #0b0f14; }
        Header { background: #111827; color: #e5e7eb; border: solid #1f2937; border-top: none; border-left: none; border-right: none; }
        Footer { background: #111827; color: #9ca3af; border: solid #1f2937; border-bottom: none; border-left: none; border-right: none; }
        DataTable { background: #0b0f14; color: #e5e7eb; border: solid #1f2937; height: 1fr; }
        DataTable > .datatable--header { background: #111827; color: #9ca3af; text-style: bold; }
        DataTable > .datatable--cursor { background: #3b82f6; color: #000; }
        """

        BINDINGS = [("q", "quit", "Salir"), ("s", "start", "Start"), ("x", "stop", "Stop"), ("r", "refresh", "Refresh")]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Static("", id="status")
            yield DataTable(id="trades")
            yield Footer()

        async def on_mount(self):
            import httpx
            self.client = httpx.AsyncClient(timeout=10.0)
            self.set_interval(5, self.fetch_data)
            table = self.query_one("#trades", DataTable)
            table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
            await self.fetch_data()

        async def on_unmount(self):
            if hasattr(self, "client"):
                await self.client.aclose()

        async def fetch_data(self):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(f"{API_BASE}/status")
                    if r.status_code == 200:
                        self.update_ui(r.json())
            except Exception as e:
                self.notify(f"Error: {e}")

        def update_ui(self, s: dict):
            bal = s.get("balance", 0)
            pnl = s.get("daily_pnl", 0)
            pnl_sign = "+" if pnl >= 0 else "-"
            trades_today = s.get("trades_today", 0)
            ticks = s.get("ticks_received", 0)
            price = s.get("last_price", 0)
            hma = s.get("last_hma", 0)
            flow = s.get("last_flow", 0)
            direction = s.get("last_direction", 0)
            mart = s.get("martingale_step", 0)
            symbol = s.get("symbol", "1HZ50V")

            # Top status bar
            self.query_one("#status", Static).update(
                f"Saldo: ${bal:,.2f}  PnL: {'+' if pnl>=0 else '-'}${abs(pnl):,.2f}  Trades: {trades_today}  Ticks: {ticks}  "
                f"Precio: {price:,.4f}  HMA: {hma:,.4f}  Flow: {flow:,.4f}  Dir: {'UP' if direction==1 else 'DOWN' if direction==-1 else 'FLAT'}  Mart: {mart}  Sym: {symbol}"
            )

            t = self.query_one("#trades", DataTable)
            t.clear()
            for tr in list(reversed(s.get("trades", [])))[:20]:
                pnl = tr.get("pnl")
                pnl_str = f"+{pnl:.2f}" if pnl and pnl > 0 else f"{pnl:.2f}" if pnl else "--"
                win = tr.get("win")
                result = "WIN" if win is True else "LOSS" if win is False else "OPEN"
                self.query_one("#trades", DataTable).add_row(
                    tr.get("entry_time", "--"),
                    tr.get("side", "--"),
                    f"{tr.get('entry_price', 0):.4f}" if tr.get("entry_price") else "--",
                    f"{tr.get('exit_price', 0):.4f}" if tr.get("exit_price") else "--",
                    f"{tr.get('stake', 0):.2f}" if tr.get("stake") else "--",
                    pnl_str,
                    "WIN" if win is True else "LOSS" if win is False else "OPEN"
                )

        async def on_mount(self):
            import httpx
            self.client = httpx.AsyncClient(timeout=10.0)
            self.set_interval(5, self.fetch_data)
            table = self.query_one("#trades", DataTable)
            table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
            await self.fetch_data()

        async def on_unmount(self):
            if hasattr(self, "client"):
                await self.client.aclose()

        async def fetch_data(self):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(f"{API_BASE}/status")
                    if r.status_code == 200:
                        self.update_ui(r.json())
            except Exception as e:
                self.notify(f"Error: {e}")

        def update_ui(self, s: dict):
            bal = s.get("balance", 0)
            pnl = s.get("daily_pnl", 0)
            pnl_sign = "+" if pnl >= 0 else "-"
            trades_today = s.get("trades_today", 0)
            ticks = s.get("ticks_received", 0)
            price = s.get("last_price", 0)
            hma = s.get("last_hma", 0)
            flow = s.get("last_flow", 0)
            direction = s.get("last_direction", 0)
            mart = s.get("martingale_step", 0)
            symbol = s.get("symbol", "1HZ50V")

            # Top status bar
            self.query_one("#status", Static).update(
                f"Saldo: ${bal:,.2f}  PnL: {'+' if pnl>=0 else '-'}${abs(pnl):,.2f}  Trades: {trades_today}  Ticks: {ticks}  "
                f"Precio: {price:,.4f}  HMA: {hma:,.4f}  Flow: {flow:,.4f}  Dir: {'UP' if direction==1 else 'DOWN' if direction==-1 else 'FLAT'}  Mart: {mart}  Sym: {symbol}"
            )

            t = self.query_one("#trades", DataTable)
            t.clear()
            for tr in list(reversed(s.get("trades", [])))[:20]:
                pnl = tr.get("pnl")
                pnl_str = f"+{pnl:.2f}" if pnl and pnl > 0 else f"{pnl:.2f}" if pnl else "--"
                win = tr.get("win")
                result = "WIN" if win is True else "LOSS" if win is False else "OPEN"
                self.query_one("#trades", DataTable).add_row(
                    tr.get("entry_time", "--"),
                    tr.get("side", "--"),
                    f"{tr.get('entry_price', 0):.4f}" if tr.get("entry_price") else "--",
                    f"{tr.get('exit_price', 0):.4f}" if tr.get("exit_price") else "--",
                    f"{tr.get('stake', 0):.2f}" if tr.get("stake") else "--",
                    pnl_str,
                    "WIN" if win is True else "LOSS" if win is False else "OPEN"
                )

        async def on_mount(self):
            import httpx
            self.client = httpx.AsyncClient(timeout=10.0)
            self.set_interval(5, self.fetch_data)
            table = self.query_one("#trades", DataTable)
            table.add_columns("Time", "Side", "Entry", "Exit", "Stake", "PnL", "Result")
            await self.fetch_data()

        async def on_unmount(self):
            if hasattr(self, "client"):
                await self.client.aclose()

        async def fetch_data(self):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(f"{API_BASE}/status")
                    if r.status_code == 200:
                        self.update_ui(r.json())
            except Exception as e:
                self.notify(f"Error: {e}")

        async def on_unmount(self):
            if hasattr(self, "client"):
                await self.client.aclose()

    app = DerivTUI()
    app.run()