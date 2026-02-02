from pydantic import BaseModel

class Config(BaseModel):
    threshold_percent: float = 0.15
    time_frame: str = "1m"
    max_symbols: int = 500
    refresh_rate: int = 13
    min_trades_count: int = 1000
    sound_alert_threshold: float = 2.0

# Глобальные переменные
current_config = Config()
scanner_active: bool = False
active_scanner = None
