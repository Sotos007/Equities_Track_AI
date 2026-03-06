import logging
import os
import sys
from dotenv import load_dotenv

# Importing local project modules
# Ensure these classes remain compatible with the existing codebase
from database import DatabaseManager
from engine import TradingEngine
from bot import InvestmentBot

# Load environment variables from .env file
load_dotenv()


def setup_logging():
    """
    Configures the professional logging system.
    Outputs to both a rotating log file and the standard system output.
    """
    log_format = '%(asctime)s - [%(levelname)s] - %(name)s: %(message)s'
    date_format = '%H:%M:%S'

    # Formatter configuration
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # File Handler: Stores logs in 'bot_activity.log' using UTF-8 encoding
    file_handler = logging.FileHandler('bot_activity.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Console Handler: Directs logs to sys.stdout for real-time monitoring
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root Logger Configuration set to INFO level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicate log entries
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Noise suppression for external libraries to maintain focus on core logic
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.ERROR)

    logging.info("Logging system initialized successfully.")


def health_check():
    """
    Performs a technical infrastructure check before system startup.
    Verifies database presence and environment configuration.
    """
    print("-" * 40)
    print("Initializing Equities Track AI Systems...")

    # Check if the database file exists in the root directory
    db_exists = os.path.exists('portfolio.db')
    # Verify if the Telegram Bot Token is loaded from .env
    token_exists = os.getenv("TELEGRAM_BOT_TOKEN") is not None

    print(f"Database Status: {'OK' if db_exists else 'NEW (Will be created)'}")
    print(f"Engine Status: Ready")
    print(f"Token Status: {'OK' if token_exists else 'MISSING'}")
    print("-" * 40)

    return token_exists


def main():
    # 1. Initialize Logging system
    setup_logging()
    logger_bot = logging.getLogger("BOT")

    # 2. Perform Pre-flight Health Check
    logger_bot.info("Running system health check...")
    if not health_check():
        logger_bot.error("Startup aborted: Missing TELEGRAM_BOT_TOKEN in .env file.")
        return

    try:
        # 3. Component Initialization
        # Instantiating core managers and engines
        logger_bot.info("Initializing system components...")

        db_mgr = DatabaseManager()
        logger_bot.info("DatabaseManager instance created.")

        engine = TradingEngine()
        logger_bot.info("TradingEngine instance created.")

        token = os.getenv("TELEGRAM_BOT_TOKEN")

        # 4. Bot Execution
        # Passing dependencies to the InvestmentBot
        logger_bot.info("Instantiating InvestmentBot with provided token and engines.")
        bot = InvestmentBot(token, db_mgr, engine)

        logger_bot.info("Systems online. Starting Bot polling...")
        bot.run()

    except KeyboardInterrupt:
        # Graceful handling of user-initiated shutdown (e.g., Ctrl+C)
        logger_bot.warning("System shutdown initiated by user.")
    except Exception as e:
        # Catch-all for critical errors to ensure they are logged before crashing
        logger_bot.critical(f"Critical system failure: {str(e)}", exc_info=True)
    finally:
        # Final log entry for session termination
        logger_bot.info("Equities Track AI session ended.")


if __name__ == '__main__':
    # Entry point of the script
    main()
