import logging
import asyncio
import pytz
from datetime import time, datetime, timedelta
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from handlers import BotHandlers

# Core watchlist for the automated scanner
WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "AMD", "MSFT",
    "GOOGL", "AMZN", "META", "NFLX", "COIN",
    "PYPL", "BABA", "PLTR", "NIO", "DIS"
]

# Initialize bot-specific logger
logger_bot = logging.getLogger("BOT")


class InvestmentBot:
    def __init__(self, token, db, engine):
        """
        Initializes the InvestmentBot with dependencies.
        :param token: Telegram Bot Token from .env
        :param db: DatabaseManager instance
        :param engine: TradingEngine instance
        """
        self.token = token
        self.db = db
        self.engine = engine
        self.handlers = BotHandlers(db, engine)

        # --- ALERT COOLDOWN LOGIC ---  
        self.last_alerts = {}
        self.alert_cooldown = timedelta(hours=4)

        logger_bot.info("InvestmentBot initialized with DB, Engine and Alert Cooldown logic.")

    async def run_scanner(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Periodically scans the WATCHLIST.
        Sleeps (no telegram messages) when market is closed or on weekends.
        """
        chat_id = self.db.get_chat_id()
        if not chat_id:
            return

        # Smart Sleep Check
        market_open = self.engine.is_market_open()

        logger_bot.info(f"Scanner: Starting bulk analysis for {len(WATCHLIST)} symbols...")
        results = await asyncio.to_thread(self.engine.analyze_watchlist_bulk, WATCHLIST)

        if not market_open:
            logger_bot.info("Scanner: Market is CLOSED. Skipping Telegram alerts (Silent Mode).")
            return

        current_time = datetime.now()

        for symbol, (sig, p) in results.items():
            last_time = self.last_alerts.get(symbol)

            if last_time and (current_time - last_time) < self.alert_cooldown:
                logger_bot.info(f"Scanner: Skipping alert for {symbol} (Cooldown active).")
                continue

            if sig != "HOLD":
                logger_bot.info(f"Scanner Signal: {symbol} identified as {sig}. Sending Alert...")
                self.last_alerts[symbol] = current_time

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 **Alert**\nSymbol: **#{symbol}**\nSignal: `{sig}` at `${p:.2f}`",
                    parse_mode='Markdown'
                )

    async def background_monitor(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Checks active portfolio for Trailing Stop conditions.
        Stays silent during weekends and off-market hours.
        """
        chat_id = self.db.get_chat_id()
        if not chat_id:
            return

        # Smart Sleep Check
        market_open = self.engine.is_market_open()

        logger_bot.info("Monitor: Fetching active portfolio for Trailing Stop checks...")
        portfolio = self.db.get_active_portfolio()
        if not portfolio:
            return

        unique_symbols = list(set(row[1] for row in portfolio))
        prices_cache = {}

        for symbol in unique_symbols:
            price = await asyncio.to_thread(self.engine.get_market_data, symbol)
            if price:
                prices_cache[symbol] = price

        for row in portfolio:
            try:
                db_id, symbol, _buy_price, _invested, peak_price = row
                current_price = prices_cache.get(symbol)

                if current_price:
                    if current_price > peak_price:
                        self.db.update_peak_price(db_id, current_price)
                        peak_price = current_price
                        logger_bot.info(f"Monitor: {symbol} (ID:{db_id}) reached new Peak: ${peak_price}")

                    # Only send Telegram message if market is open
                    if market_open:
                        drop = ((peak_price - current_price) / peak_price) * 100
                        if drop >= 5.0:
                            logger_bot.warning(f"Monitor: Trailing Stop triggered for {symbol} (-{drop:.2f}%)")
                            msg = (f"🛡️ **Trailing Stop Alert**\n\n"
                                   f"Symbol: **{symbol}**\n"
                                   f"Peak: `${peak_price:.2f}`\n"
                                   f"Now: `${current_price:.2f}`\n"
                                   f"Drop: `{drop:.2f}%` 🧨")
                            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
                    else:
                        logger_bot.info(f"Monitor: Market closed. Silent tracking for {symbol}.")
            except Exception as e:
                logger_bot.error(f"Monitor Error for record ID {row[0]}: {str(e)}")

    @staticmethod
    async def error_handler(_update: object, context: ContextTypes.DEFAULT_TYPE):
        if "httpx.ReadError" in str(context.error):
            logger_bot.warning("Network: Connection interrupted. Reconnecting...")
        else:
            logger_bot.error(f"System: Unexpected error occurred: {context.error}")

    async def send_daily_report(self, context: ContextTypes.DEFAULT_TYPE):
        chat_id = self.db.get_chat_id()
        if not chat_id:
            return

        logger_bot.info("Report: Generating daily performance summary...")
        data = self.db.get_active_portfolio()
        if not data:
            return

        unique_symbols = list(set(row[1] for row in data))
        prices_cache = {}
        for s in unique_symbols:
            p = await asyncio.to_thread(self.engine.get_market_data, s)
            if p:
                prices_cache[s] = p

        total_daily_pnl = 0
        perf_data = []

        for row in data:
            symbol, buy_price, invested = row[1], row[2], row[3]
            current_price = prices_cache.get(symbol)

            if current_price:
                p_pct = ((current_price - buy_price) / buy_price) * 100
                total_daily_pnl += (invested * p_pct) / 100
                perf_data.append({"s": symbol, "p": p_pct})

        if not perf_data:
            return

        perf_data.sort(key=lambda x: x['p'])

        summary = (
            f"🌙 **Daily Market Recap**\n"
            f"----------------------------\n"
            f"💰 Total P/L: `${total_daily_pnl:+.2f}`\n"
            f"🚀 Top: **{perf_data[-1]['s']}** ({perf_data[-1]['p']:+.2f}%)\n"
            f"📉 Worst: **{perf_data[0]['s']}** ({perf_data[0]['p']:+.2f}%)\n"
            f"----------------------------"
        )
        await context.bot.send_message(chat_id=chat_id, text=summary, parse_mode='Markdown')
        logger_bot.info("Report: Daily summary sent successfully.")

    def run(self):
        app = ApplicationBuilder().token(self.token).build()
        app.add_error_handler(self.error_handler)

        app.add_handler(CommandHandler("start", self.handlers.start))
        app.add_handler(CommandHandler("help", self.handlers.help_command))
        app.add_handler(CommandHandler("analyze", self.handlers.analyze))
        app.add_handler(CommandHandler("bought", self.handlers.bought))
        app.add_handler(CommandHandler("sold", self.handlers.sold))
        app.add_handler(CommandHandler("portfolio", self.handlers.portfolio))
        app.add_handler(CommandHandler("status", self.handlers.status))
        app.add_handler(CommandHandler("report", self.handlers.report))
        app.add_handler(CommandHandler("myid", self.handlers.get_my_id))
        app.add_handler(CallbackQueryHandler(self.handlers.status_refresh_callback, pattern="refresh_status"))

        jq = app.job_queue
        jq.run_repeating(self.run_scanner, interval=900, first=10)
        jq.run_repeating(self.background_monitor, interval=1200, first=20)

        at_time = time(23, 0, 0, tzinfo=pytz.timezone('Europe/Athens'))
        jq.run_daily(self.send_daily_report, time=at_time)

        logger_bot.info("Bot: Starting polling. All systems active with Smart Sleep.")
        app.run_polling()
