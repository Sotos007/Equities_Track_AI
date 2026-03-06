import logging
import pytz
import yfinance as yf
from datetime import datetime

# Initialize engine-specific logger
logger_engine = logging.getLogger("ENGINE")


class TradingEngine:
    def __init__(self):
        """
        Initializes the Trading Engine with the Wall Street timezone (EST/EDT).
        This ensures all market open/close logic is synchronized with NYSE/NASDAQ.
        """
        self.market_tz = pytz.timezone('America/New_York')
        logger_engine.info("Trading Engine initialized with New York Timezone.")

    def is_market_open(self):
        """
        Checks if the New York Stock Exchange is currently open.
        Operating hours: Monday to Friday, 09:30 - 16:00 EST.
        """
        now = datetime.now(self.market_tz)

        # Check if today is a weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5

        # Define market hours for the current day
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)

        # Determine if current time falls within market hours
        open_status = is_weekday and (market_start <= now <= market_end)

        if not open_status:
            logger_engine.info(f"Market is currently CLOSED ({now.strftime('%H:%M')} EST)")

        return open_status

    @staticmethod
    def analyze_watchlist_bulk(symbols):
        """
        Analyzes an entire list of symbols in a single API call to optimize performance.
        Calculates RSI and EMA for each ticker to generate Buy/Sell signals.
        """
        logger_engine.info(f"BULK_SCAN: Fetching data for {len(symbols)} symbols...")
        try:
            # Batch download 3 months of data for all symbols
            data = yf.download(symbols, period="3mo", group_by='ticker', progress=False)
            results = {}

            for symbol in symbols:
                # Handle single vs multi-symbol dataframe structure from yfinance
                df = data[symbol] if len(symbols) > 1 else data

                # Ensure we have enough data points for indicators (at least 20 for EMA20)
                if df.empty or len(df) < 20:
                    logger_engine.warning(f"BULK_SCAN: Insufficient data for {symbol}")
                    continue

                # Technical Indicator Logic: RSI (14 periods)
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

                # Avoid division by zero by replacing 0 loss with a tiny value
                rs = gain / loss.replace(0, 0.001)
                rsi = 100 - (100 / (1 + rs)).iloc[-1]

                # Technical Indicator Logic: EMA (20 periods)
                ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                price = df['Close'].iloc[-1]

                # Signal Logic:
                # BUY: Oversold (RSI < 35) but price remains above EMA20 (Bullish trend)
                # SELL: Overbought (RSI > 65) but price drops below EMA20 (Bearish trend)
                if rsi < 35 and price > ema20:
                    results[symbol] = ("BUY", round(float(price), 2))
                elif rsi > 65 and price < ema20:
                    results[symbol] = ("SELL", round(float(price), 2))

            return results
        except Exception as e:
            logger_engine.error(f"BULK_ERROR: {str(e)}")
            return {}

    def get_market_data(self, symbol):
        """
        Retrieves the latest price for a symbol with safe conversion from Series/Dataframe to Float.
        Adjusts polling frequency/interval based on market status.
        """
        symbol_upper = symbol.upper()
        market_is_open = self.is_market_open()

        try:
            if market_is_open:
                # Use 1-minute interval for real-time tracking during market hours
                logger_engine.info(f"API_CALL: Market is OPEN. Fetching 1m data for {symbol_upper}...")
                df = yf.download(symbol_upper, period="1d", interval="1m", progress=False)
            else:
                # Use daily interval to get the last known close price when market is shut
                logger_engine.info(f"API_CALL: Market is CLOSED. Fetching last close for {symbol_upper}...")
                df = yf.download(symbol_upper, period="5d", interval="1d", progress=False)

            if df is not None and not df.empty:
                # Extraction fix: Safely get the raw price value from the Series
                last_row = df['Close'].values[-1]

                # Check if data is returned as an array/list (common with MultiIndex)
                if hasattr(last_row, "__len__"):
                    current_price = float(last_row[0])
                else:
                    current_price = float(last_row)

                # Filter out clearly erroneous data points
                if current_price > 0 and current_price != 1.45:
                    logger_engine.info(f"DATA_RECV: {symbol_upper} price confirmed: ${current_price:.2f}")
                    return round(current_price, 2)

            # Fallback Mechanism: Use Ticker.fast_info if standard download fails
            logger_engine.info(f"FALLBACK: Standard download failed for {symbol_upper}, checking fast_info...")
            ticker = yf.Ticker(symbol_upper)
            if ticker.fast_info and 'lastPrice' in ticker.fast_info:
                f_price = ticker.fast_info['lastPrice']
                if f_price and f_price > 0:
                    return round(float(f_price), 2)

            return None

        except Exception as e:
            logger_engine.error(f"API_ERROR for {symbol_upper}: {str(e)}")
            return None

    @staticmethod
    def validate_symbol(symbol):
        """
        Strict validation of a stock symbol by attempting to fetch historical data.
        Returns True only if data is successfully retrieved.
        """
        symbol_upper = symbol.upper()
        try:
            ticker = yf.Ticker(symbol_upper)
            # Requesting 1 day of history; if ticker is invalid, dataframe will be empty
            df = ticker.history(period="1d")
            if not df.empty:
                logger_engine.info(f"VALIDATION_SUCCESS: Symbol {symbol_upper} is valid.")
                return True

            logger_engine.warning(f"VALIDATION_FAIL: Symbol {symbol_upper} not found or delisted.")
            return False
        except Exception as e:
            logger_engine.error(f"VALIDATION_ERROR for {symbol_upper}: {str(e)}")
            return False

    @staticmethod
    def analyze_trend(symbol):
        """
        Performs technical analysis (RSI & EMA) for a single ticker.
        Requires 3 months of historical data for reliable calculation of indicators.
        """
        symbol_upper = symbol.upper()
        try:
            ticker = yf.Ticker(symbol_upper)
            # Fetching 3mo data to ensure EMA20 and RSI14 stability
            df = ticker.history(period="3mo")

            if df.empty or len(df) < 20:
                logger_engine.warning(f"ANALYZE_SKIP: Insufficient historical data for {symbol_upper}")
                return "HOLD", None

            # RSI Calculation (Relative Strength Index)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

            # Handle division by zero
            rs = gain / loss.replace(0, 0.001)
            rsi_series = 100 - (100 / (1 + rs))

            # EMA20 Calculation (Exponential Moving Average)
            ema20_series = df['Close'].ewm(span=20, adjust=False).mean()

            # Latest indicator values
            current_p = round(float(df['Close'].iloc[-1]), 2)
            current_rsi = float(rsi_series.iloc[-1])
            current_ema = float(ema20_series.iloc[-1])

            logger_engine.info(
                f"TECH_SCAN {symbol_upper}: Price=${current_p}, RSI={current_rsi:.2f}, EMA20=${current_ema:.2f}")

            # Signal Logic Execution
            if current_rsi < 35 and current_p > current_ema:
                return "BUY", current_p
            elif current_rsi > 65 and current_p < current_ema:
                return "SELL", current_p
            else:
                return "HOLD", current_p

        except Exception as e:
            logger_engine.error(f"ANALYZE_ERROR for {symbol_upper}: {str(e)}")
            return "HOLD", None
