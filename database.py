import sqlite3
import logging
from datetime import datetime

# Initialize database-specific logger
logger_db = logging.getLogger("DATABASE")


class DatabaseManager:
    def __init__(self, db_name="portfolio.db"):
        """
        Initializes the Database Manager.
        :param db_name: The filename of the SQLite database.
        """
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        """
        Initializes the database schema if it doesn't exist.
        Creates 'portfolio' for trade tracking and 'settings' for bot configuration.
        """
        logger_db.info("Database: Initializing professional schema...")
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()

                # Portfolio Table: Tracks active and closed positions with Trailing Stop (peak_price) support
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS portfolio (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        buy_price REAL NOT NULL,
                        invested_amount REAL DEFAULT 0,
                        peak_price REAL DEFAULT 0,
                        purchase_date TEXT NOT NULL,
                        sell_price REAL,
                        sell_date TEXT,
                        profit_loss REAL,
                        status TEXT DEFAULT 'ACTIVE'
                    )
                ''')

                # Settings Table: Stores persistent configuration like Chat ID and bot preferences
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                conn.commit()
            logger_db.info("Database: Schema is ready and verified.")
        except sqlite3.Error as e:
            logger_db.error(f"DB_INIT_ERROR: Failed to initialize schema: {e}")

    def add_transaction(self, symbol, buy_price, invested_amount):
        """
        Records a new purchase and initializes the Peak Price for trailing stop logic.
        """
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbol = symbol.upper()

        logger_db.info(f"DB: Recording new transaction for {symbol} at ${buy_price}...")
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO portfolio 
                       (symbol, buy_price, invested_amount, peak_price, purchase_date, status) 
                       VALUES (?, ?, ?, ?, ?, 'ACTIVE')""",
                    (symbol, buy_price, invested_amount, buy_price, date_str)
                )
                conn.commit()
            logger_db.info(f"DB_SUCCESS: {symbol} successfully added to active portfolio.")
        except sqlite3.Error as e:
            logger_db.error(f"DB_WRITE_ERROR for {symbol}: {e}")

    def update_peak_price(self, db_id, new_peak):
        """
        Updates the highest recorded price (Peak) for a specific position (Trailing Stop logic).
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE portfolio SET peak_price = ? WHERE id = ?", (new_peak, db_id))
                conn.commit()
            logger_db.info(f"DB_UPDATE: Peak price for ID {db_id} updated to ${new_peak:.2f}")
        except sqlite3.Error as e:
            logger_db.error(f"DB_UPDATE_ERROR for ID {db_id}: {e}")

    def get_active_portfolio(self):
        """
        Retrieves all active positions for the monitor service and status reports.
        """
        logger_db.info("DB: Fetching all active portfolio positions...")
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, symbol, buy_price, invested_amount, peak_price FROM portfolio WHERE status='ACTIVE'"
                )
                results = cursor.fetchall()
                logger_db.info(f"DB_READ: Retrieved {len(results)} active positions.")
                return results
        except sqlite3.Error as e:
            logger_db.error(f"DB_READ_ERROR: Failed to fetch portfolio: {e}")
            return []

    def close_position(self, symbol, sell_price):
        """
        Closes an active position, records the exit price, and calculates final P/L percentage.
        """
        sell_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbol = symbol.upper()

        logger_db.info(f"DB: Attempting to close position for {symbol} at ${sell_price}...")
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # Find the original purchase price to calculate profit/loss
                cursor.execute("SELECT buy_price FROM portfolio WHERE symbol=? AND status='ACTIVE'", (symbol,))
                row = cursor.fetchone()

                if row:
                    buy_price = row[0]
                    pnl = ((sell_price - buy_price) / buy_price) * 100
                    cursor.execute('''
                        UPDATE portfolio SET status='CLOSED', sell_price=?, sell_date=?, profit_loss=? 
                        WHERE symbol=? AND status='ACTIVE'
                    ''', (sell_price, sell_date, pnl, symbol))
                    conn.commit()
                    logger_db.info(f"DB_SUCCESS: Closed {symbol} with final P/L of {pnl:.2f}%.")
                    return pnl

                logger_db.warning(f"DB_CLOSE_SKIP: No active position found for {symbol}.")
                return None
        except sqlite3.Error as e:
            logger_db.error(f"DB_CLOSE_ERROR for {symbol}: {e}")
            return None

    def get_trade_history(self):
        """
        Retrieves the history of all closed positions, ordered by the most recent exit.
        """
        logger_db.info("DB: Retrieving closed trade history...")
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT symbol, buy_price, sell_price, profit_loss, sell_date 
                    FROM portfolio WHERE status='CLOSED' ORDER BY sell_date DESC
                ''')
                results = cursor.fetchall()
                logger_db.info(f"DB_HISTORY: Found {len(results)} historical trades.")
                return results
        except sqlite3.Error as e:
            logger_db.error(f"DB_HISTORY_ERROR: {e}")
            return []

    def save_chat_id(self, chat_id):
        """
        Persistently saves the Telegram Chat ID to the settings table for background notifications.
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # Use INSERT OR REPLACE to ensure only one chat_id exists for alerts
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('chat_id', ?)", (str(chat_id),))
                conn.commit()
            logger_db.info(f"DB_SETTINGS: Chat ID {chat_id} successfully registered.")
        except sqlite3.Error as e:
            logger_db.error(f"DB_SETTINGS_ERROR: Failed to save Chat ID: {e}")

    def get_chat_id(self):
        """
        Retrieves the stored Chat ID for background monitoring jobs.
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key='chat_id'")
                row = cursor.fetchone()
                if row:
                    return int(row[0])
                return None
        except sqlite3.Error as e:
            logger_db.error(f"DB_SETTINGS_READ_ERROR: {e}")
            return None
