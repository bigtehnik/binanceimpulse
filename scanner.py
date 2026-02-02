import json
import asyncio
import aiohttp
import websockets
from datetime import datetime, timedelta, timezone
from fastapi import WebSocket
import app.config as config

class Scanner:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.signals = []
        self.last_update = datetime.now()

    async def get_top_symbols(self):
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        usdt = [s for s in data if s['symbol'].endswith('USDT')]
        sorted_ = sorted(usdt, key=lambda x: float(x['quoteVolume']), reverse=True)
        return [s['symbol'] for s in sorted_[:config.current_config.max_symbols]]

    async def run(self):
        while config.scanner_active:
            try:
                await self.websocket.send_json({"type": "scan_start"})
                symbols = await self.get_top_symbols()
                streams = [f"{s.lower()}@kline_{config.current_config.time_frame}" for s in symbols]
                url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
                async with websockets.connect(url) as conn:
                    while config.scanner_active:
                        try:
                            raw = await asyncio.wait_for(conn.recv(), timeout=30)
                            k = json.loads(raw)['data']['k']
                            if k['x']:
                                await self.process_signal(k)
                            if (datetime.now() - self.last_update).seconds >= config.current_config.refresh_rate:
                                await self.update_client()
                                self.last_update = datetime.now()
                        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                            await asyncio.sleep(5)
                            break
                        except Exception:
                            await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(5)
            finally:
                await self.websocket.send_json({"type": "scan_end"})

    async def process_signal(self, kline: dict):
        try:
            high, low = float(kline['h']), float(kline['l'])
            change = (high - low) / low * 100
            trades = int(kline['n'])
            cfg = config.current_config

            if change >= cfg.threshold_percent and trades >= cfg.min_trades_count:
                utc = datetime.fromtimestamp(kline['t']/1000)
                display_time = utc.astimezone(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
                sym = kline['s']
                sig = {
                    'symbol': sym,
                    'time': display_time,
                    'change': change,
                    'change_str': f"{change:.2f}%",
                    'trend': "🟢" if float(kline['c']) > float(kline['o']) else "🔴"
                }
                # обновляем или добавляем
                idx = next((i for i, s in enumerate(self.signals) if s['symbol']==sym), None)
                if idx is not None:
                    self.signals[idx].update(sig)
                else:
                    self.signals.append(sig)
                await self.websocket.send_json({"type": "signal", "signal": sig})
        except Exception:
            pass  # игнорируем ошибки обработки одного сигнала

    async def update_client(self):
        for s in self.signals:
            await self.websocket.send_json({"type": "signal", "signal": s})
