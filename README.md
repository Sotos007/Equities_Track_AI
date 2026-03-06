![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Telegram](https://img.shields.io/badge/bot-telegram-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Database](https://img.shields.io/badge/database-SQLite-lightgrey.svg)
![Finance](https://img.shields.io/badge/API-Yahoo%20Finance-red.svg)

# 📈 Market Hunter AI

---
A professional-grade Telegram Bot for real-time stock market monitoring, technical analysis, and portfolio tracking.

## ✨ Key Features
- **Real-time Analysis**: Monitor symbols with RSI and EMA20 signals.
- **Automated Alerts**: Trailing stop loss protection (triggers at 5% drop).
- **Portfolio Tracking**: Manage your bought/sold positions with a clean dashboard.
- **Daily Recap**: Automatic EOD summaries of your portfolio performance.

## 🧠 Trading Logic
- **Technical Analysis**: The bot uses a combination of **RSI (Relative Strength Index)** and **EMA20 (Exponential Moving Average)** to determine market trends.
- **Trailing Stop Mechanism**: Once a position is opened, the bot tracks the highest price reached (Peak). If the price drops more than 5% from that peak, an automated alert is triggered to protect profits.
- **Async Execution**: Built with `asyncio` to handle multiple API requests and background monitoring without blocking the main bot interactions.

## 🛡️ Stability & Security
- **Strict Validation**: Prevents database errors by verifying symbols via Yahoo Finance API before any operation.
- **Resilience**: Custom error handlers manage network issues (httpx exceptions) without crashing.
- **Market Hours Awareness**: Smart switching between live and closing data.

## 📁 Project Structure
- `main.py`: The entry point of the application. Starts the Telegram bot.
- `bot.py`: Core bot logic, job queues, and background task scheduling. 
- `engine.py`: Market data retrieval and technical analysis logic. 
- `handlers.py`: Telegram command handlers and user interaction logic. 
- `database.py`: SQLite database management and position tracking.

---

## 🧮 Calculation Logic

The bot follows standardized financial formulas to ensure data accuracy:

| Metric                            | Formula                              | Goal                                                      |
|:----------------------------------|:-------------------------------------|:----------------------------------------------------------|
| **Profit & Loss (P/L)**           | `((Current - Buy) / Buy) * 100`      | Measures current investment return.                       |
| **Trailing Stop**                 | `((Peak - Current) / Peak) * 100`    | Monitors price drop from the highest point.               |
| **EMA 20**                        | `(Price * K) + (Prev_EMA * (1 - K))` | Detects trends with emphasis on recent data.              |
| **Position Sizing**               | `Invested / Buy_Price`               | Calculates exact quantity of shares held.                 |
| **RSI (Relative Strength Index)** | `100 - (100 / (1 + RS))`             | Identifies overbought (>70) or oversold (<30) conditions. |
> 💡 **Note:** The Trailing Stop triggers an automated alert when the price drop is **≥ 5.0%** from its peak.

---

## 🔑 How to get your Telegram Bot Token

To use this bot, you need to create your own bot instance on Telegram:

1.  Open Telegram and search for **@BotFather**.
2.  Start a chat and send the command `/newbot`.
3.  Follow the instructions to give your bot a **name** and a **username**.
4.  Once created, BotFather will provide an **API Token**.
5.  Copy this token and paste it into your `.env` file as `TELEGRAM_TOKEN=your_token_here`.
6. **Important**: Once the bot is running, you **must** send the `/start` command to it. This allows the bot to save your Chat ID and enable automated market alerts.


---

## 📖 Bot Commands

Below is a list of available commands with examples of how to use them:

- **/start** - Initialize the bot and receive a welcome message.
- **/help** - Display detailed usage instructions.

- **/analyze `[SYMBOL]`** - Technical analysis (RSI & EMA20).
  * *Example:* `/analyze TSLA`

- **/bought `[SYMBOL]` `[PRICE CURRENT]` `[AMOUNT INVETS]`** - Record a new purchase. 
  * *Example:* `/bought AAPL 150.50 500` (Buys $500 worth of AAPL at $150.50)

- **/sold `[SYMBOL]` `[PRICE]`** - Close an active position.
  * *Example:* `/sold NVDA 820.10` (Sells NVDA at $820.10)

- **/status** - View live portfolio performance with real-time price updates.
- **/portfolio** - List all currently active positions.
- **/report** - View historical trade performance summary.
- **/myid** - Get your Telegram Chat ID for automated alerts.

---

## 🚀 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Sotos007/Equities_Track_AI.git
2. Install dependencies: 
   ```bash
   pip install -r requirements.txt
3. Create a .env file in the root directory and add your bot token:
   ```env
   TELEGRAM_TOKEN=your_bot_token_here
4. Run the application:
   python main.py

---
## ⚠️ Disclaimer
This bot is for **educational and informational purposes only**. It does not constitute financial advice. Always perform your own due diligence before making any investment decisions. The author is not responsible for any financial losses incurred through the use of this software.