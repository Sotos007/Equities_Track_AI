import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Message
from telegram.ext import ContextTypes

# Initialize bot logger for tracking command execution
logger_bot = logging.getLogger("BOT")


class BotHandlers:
    def __init__(self, db, engine):
        """
        Initializes handlers with database and engine dependencies.
        :param db: DatabaseManager instance
        :param engine: TradingEngine instance
        """
        self.db = db
        self.engine = engine

    @staticmethod
    async def get_my_id(update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Displays and logs the user's Telegram Chat ID.
        Essential for setting up automated alerts in the .env or database.
        """
        if update.effective_chat:
            chat_id = update.effective_chat.id
            user_name = update.effective_user.first_name if update.effective_user else "User"
            logger_bot.info(f"👤 USER_IDENT: {user_name} (ID: {chat_id}) requested identification.")

            await update.message.reply_text(
                f"🆔 **Your Chat ID is:** `{chat_id}`\n\n"
                "The Bot now recognizes you, and automated notifications are active!",
                parse_mode='Markdown'
            )

    async def start(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Initializes the Bot session and persists the Chat ID for background jobs.
        Sets up the persistent reply keyboard for easy navigation.
        """
        if update.effective_chat:
            chat_id = update.effective_chat.id
            logger_bot.info(f"🚀 START: Initializing session for Chat ID {chat_id}")
            self.db.save_chat_id(chat_id)

            # Define main menu buttons
            buttons = [['/status', '/portfolio'], ['/report', '/help']]
            await update.message.reply_text(
                "🚀 **Market Hunter AI Active.**\n\nUse the menu below to manage your portfolio and track market opportunities.",
                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
                parse_mode='Markdown'
            )

    @staticmethod
    async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Displays the command manual to the user.
        """
        help_text = (
            "📖 **Command Manual:**\n\n"
            "1️⃣ **/analyze [SYMBOL]** - RSI/EMA Technical Scan\n"
            "2️⃣ **/bought [SYM] [PRC] [AMT]** - Record new position\n"
            "3️⃣ **/sold [SYM] [PRC]** - Close active position\n"
            "4️⃣ **/status** - Live P/L & Performance\n"
            "5️⃣ **/portfolio** - Quick list of holdings\n"
            "6️⃣ **/report** - Historical trade performance\n"
            "7️⃣ **/myid** - Get your Telegram Chat ID"
        )
        if update.message:
            logger_bot.info("HELP: User requested command manual.")
            await update.message.reply_text(help_text, parse_mode='Markdown')

    async def analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Executes technical analysis using real-time market data.
        Returns BUY/SELL/HOLD signals based on RSI and EMA20 indicators.
        """
        if not context.args or not update.message:
            if update.message:
                await update.message.reply_text("⚠️ **Usage:** `/analyze [SYMBOL]`", parse_mode='Markdown')
            return

        symbol = context.args[0].upper()
        logger_bot.info(f"ANALYZE: Performing technical scan for {symbol}...")
        wait_msg = await update.message.reply_text(f"🔍 Searching and analyzing {symbol}...")

        # 1. Fetch current market price using the TradingEngine
        price = await asyncio.to_thread(self.engine.get_market_data, symbol)

        if price is None:
            logger_bot.warning(f"ANALYZE_FAIL: {symbol} not found or API error.")
            await wait_msg.edit_text(f"❌ Symbol **{symbol}** not found or market is closed.",
                                     parse_mode='Markdown')
            return

        # 2. Execute technical trend analysis
        sig, _ = await asyncio.to_thread(self.engine.analyze_trend, symbol)

        # 3. Present results with visual indicators
        emoji = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
        logger_bot.info(f"ANALYZE_SUCCESS: {symbol} resulted in {sig} signal.")

        await wait_msg.edit_text(
            f"📊 **Analysis: {symbol}**\n\n"
            f"💵 Current Price: `${price:.2f}`\n"
            f"🎯 Signal: {emoji} **{sig}**",
            parse_mode='Markdown'
        )

    async def bought(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Records a new purchase after validating the symbol's existence.
        Ensures strict data types for price and investment amounts.
        """
        try:
            if not update.message or len(context.args) < 3:
                await update.message.reply_text("⚠️ **Usage:** `/bought [SYMBOL] [PRICE] [MONEY]`",
                                                parse_mode='Markdown')
                return

            symbol = context.args[0].upper()

            # Sanitize numeric input (support for both '.' and ',' decimal separators)
            try:
                price = float(context.args[1].replace(',', '.'))
                money = float(context.args[2].replace(',', '.'))
            except ValueError:
                await update.message.reply_text("❌ **Error:** Price and Money must be numeric values.")
                return

            # STEP 1: Strict Validation via Engine
            status_msg = await update.message.reply_text(f"🔍 Verifying symbol {symbol}...")
            is_valid = await asyncio.to_thread(self.engine.validate_symbol, symbol)

            if not is_valid:
                logger_bot.warning(f"BOUGHT_REJECTED: {symbol} validation failed.")
                await status_msg.edit_text(f"❌ Symbol {symbol} was rejected or does not exist.")
                return

            # STEP 2: Database commit
            self.db.add_transaction(symbol, price, money)
            logger_bot.info(f"BOUGHT_LOGGED: {symbol} added at ${price} with ${money} investment.")
            await status_msg.edit_text(f"✅ Purchase of **{symbol}** successfully recorded!")

        except Exception as e:
            logger_bot.error(f"HANDLER_ERROR in 'bought': {str(e)}")
            if update.message:
                await update.message.reply_text("❌ An unexpected error occurred while saving the transaction.")

    async def status(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Generates and displays the Live Portfolio Status.
        Includes an Inline Keyboard for price refreshing.
        """
        if not update.effective_user or not update.message:
            return

        logger_bot.info(f"STATUS_REQUEST: Generating live report for User {update.effective_user.id}")
        await update.get_bot().send_chat_action(chat_id=update.effective_chat.id, action="typing")

        text = await self._generate_status_text()
        keyboard = [[InlineKeyboardButton("🔄 Refresh Prices", callback_data="refresh_status")]]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def _generate_status_text(self):
        """
        Internal logic for generating the Portfolio UI text.
        Calculates Profit/Loss and Drawdown from Peak for each active position.
        """
        data = self.db.get_active_portfolio()
        if not data:
            return "ℹ️ **Your portfolio is currently empty.**"

        unique_symbols = list(set(row[1] for row in data))
        prices_cache = {}

        # Bulk fetch current prices to optimize API calls
        for symbol in unique_symbols:
            price = await asyncio.to_thread(self.engine.get_market_data, symbol)
            if price:
                prices_cache[symbol] = price

        report = f"📊 **LIVE MARKET PORTFOLIO**\n"
        report += f"`🕒 {datetime.now().strftime('%H:%M:%S')}`\n"
        report += "————————————————————\n\n"

        total_pnl_cash = 0
        total_invested = 0

        for row in data:
            # Row mapping: id, symbol, buy_price, invested, peak_price
            symbol, buy_price, invested, peak_price = row[1], row[2], row[3], row[4]
            total_invested += invested
            current_price = prices_cache.get(symbol)

            if current_price:
                pnl_pct = ((current_price - buy_price) / buy_price) * 100
                pnl_cash = (invested * pnl_pct) / 100
                total_pnl_cash += pnl_cash

                # Calculation of drawdown from the peak price recorded by the monitor
                current_peak = max(peak_price, current_price)
                drawdown_val = ((current_peak - current_price) / current_peak) * 100

                emoji = "✅" if pnl_pct >= 0 else "🔻"
                trend = "📈" if pnl_pct >= 0 else "📉"

                report += f"{emoji} **{symbol}**\n"
                report += f"   ├ {trend} P/L: `{pnl_cash:+.2f}$` ({pnl_pct:+.2f}%)\n"
                report += f"   ├ 💵 Price: `${current_price:.2f}`\n"
                report += f"   └ 📉 Drop: `{drawdown_val:.1f}%` from peak\n\n"

        avg_perf = (total_pnl_cash / total_invested * 100) if total_invested > 0 else 0
        report += "————————————————————\n"
        report += f"💰 **Total P/L: `{total_pnl_cash:+.2f}$`**\n"
        report += f"📊 **Return: `{avg_perf:+.2f}%`**\n"
        report += f"🏦 **Equity: `${total_invested:.2f}`**"

        return report

    async def status_refresh_callback(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Handles the 'Refresh' button callback.
        Updates the existing status message with new market data.
        """
        query = update.callback_query
        if not query or not query.message:
            return

        await query.answer("🔄 Updating market data...")
        new_text = await self._generate_status_text()

        message = query.message
        if isinstance(message, Message):
            try:
                # Update the message text while keeping the refresh button
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=message.reply_markup,
                    parse_mode='Markdown'
                )
                logger_bot.info("STATUS_REFRESH: Dashboard updated via callback.")
            except Exception as e:
                logger_bot.debug(f"REFRESH_SKIP: No changes detected or error: {e}")

    async def portfolio(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Quick portfolio overview without live price fetching.
        Fast response for checking invested amounts and purchase prices.
        """
        data = self.db.get_active_portfolio()
        if not data or not update.message:
            if update.message:
                await update.message.reply_text("📁 Portfolio is currently empty.")
            return

        logger_bot.info("PORTFOLIO: Listing active positions (Static).")
        msg = "📂 **Active Holdings:**\n\n"
        total = 0
        for row in data:
            symbol, buy, inv = row[1], row[2], row[3]
            total += inv
            msg += f"🔹 **{symbol}**\n   `Inv: ${inv:.2f} | Buy: ${buy:.2f}`\n\n"

        msg += f"————————————————————\n💰 **Total Invested Capital: ${total:.2f}**"
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def sold(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Closes an active position and calculates final performance.
        Requires symbol validation to prevent accidental deletions.
        """
        try:
            if not update.message or not context.args:
                return

            symbol = context.args[0].upper()
            sell_price = float(context.args[1].replace(',', '.'))

            # Validate symbol before proceeding with DB closure
            is_valid = await asyncio.to_thread(self.engine.validate_symbol, symbol)
            if not is_valid:
                await update.message.reply_text(f"❌ Symbol {symbol} is invalid.")
                return

            pnl = self.db.close_position(symbol, sell_price)
            if pnl is not None:
                logger_bot.info(f"SOLD: {symbol} closed at ${sell_price} with {pnl:.2f}% P/L.")
                emoji = "💰" if pnl >= 0 else "📉"
                await update.message.reply_text(f"✅ **{symbol} Sold!**\n\nFinal Performance: {emoji} `{pnl:.2f}%`",
                                                parse_mode='Markdown')
            else:
                logger_bot.warning(f"SOLD_FAIL: No active position found for {symbol}.")
                await update.message.reply_text(f"❌ No active position found for {symbol}.")

        except (ValueError, IndexError):
            if update.message:
                await update.message.reply_text("⚠️ **Usage:** `/sold [SYMBOL] [PRICE]`")

    async def report(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """
        Retrieves and displays the historical record of all closed transactions.
        """
        hist = self.db.get_trade_history()
        if not update.message:
            return

        logger_bot.info("REPORT: Generating historical trade report.")
        if hist:
            total_pnl = sum(row[3] for row in hist)
            await update.message.reply_text(f"📜 **Trade History:**\nCumulative Performance: `{total_pnl:.2f}%`",
                                            parse_mode='Markdown')
            # You could add a detailed list of last 5-10 trades here if needed
        else:
            await update.message.reply_text("📭 No trade history available yet.")