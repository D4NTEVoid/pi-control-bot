# Pi Control Bot

**Monitor your Raspberry Pi remotely through Telegram.**

Pi Control Bot is a lightweight Python application that provides a Telegram-based interface for monitoring Raspberry Pi hardware and system resources.

It retrieves device metrics and network information, allowing authorized users to inspect their Raspberry Pi through Telegram commands and an interactive inline keyboard.

## Features

- **Public IP monitoring:** Retrieve the device's public IPv4 address.
- **CPU temperature:** Read the current CPU temperature.
- **Voltage monitoring:** Retrieve voltage information through `vcgencmd`.
- **CPU and RAM monitoring:** Display current processor and memory utilization.
- **GPU information:** Retrieve available GPU memory and SoC core clock information.
- **Fan monitoring:** Read fan RPM when exposed through Linux hardware monitoring interfaces.
- **Storage monitoring:** Display filesystem usage.
- **Interactive Telegram menu:** Access monitoring commands through inline keyboard buttons.
- **Access control:** Restrict bot usage to authorized Telegram chat IDs.
- **Automatic polling:** Receive and process Telegram updates without requiring a public-facing server.

## Supported Commands

| Command | Description |
|---|---|
| `/start` | Display the interactive menu |
| `/ip` | Retrieve public IPv4 address |
| `/voltage` | Retrieve voltage information |
| `/temp` | Display CPU temperature |
| `/status` | Display CPU, RAM, and GPU information |
| `/fan` | Retrieve fan RPM |
| `/storage` | Display disk usage |

## Requirements

- Raspberry Pi running Linux
- Python 3.9+
- Telegram bot token
- `requests`
- `psutil`
- `vcgencmd` for supported hardware metrics

Some hardware metrics depend on the Raspberry Pi model, kernel, firmware, and installed drivers.

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/pi-control-bot.git
cd pi-control-bot
```

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Configuration

Create a configuration file:

```bash
cp .env.example .env
```

Set your Telegram bot token and authorized chat IDs:

```dotenv
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
AUTHORIZED_CHAT_IDS=YOUR_TELEGRAM_CHAT_ID
```

The bot reads environment variables directly and does not automatically load `.env`.

Load the configuration:

```bash
set -a
source .env
set +a
```

Start the bot:

```bash
python3 pi_control_bot.py
```

## Access Control

The bot uses Telegram chat IDs to restrict access.

Only chat IDs listed in `AUTHORIZED_CHAT_IDS` can execute monitoring commands or use inline keyboard callbacks.

Multiple authorized chat IDs can be provided as a comma-separated list:

```dotenv
AUTHORIZED_CHAT_IDS=123456789,987654321
```

Do not expose your Telegram bot token or allow unauthorized users to access your bot.

## Hardware Compatibility

Some metrics depend on hardware and operating-system support.

- CPU temperature can be obtained through `vcgencmd` or Linux thermal-zone interfaces.
- Voltage information depends on `vcgencmd` support.
- Fan RPM requires a compatible hardware monitoring sensor exposed through `/sys/class/hwmon/`.
- GPU memory allocation and clock reporting vary between Raspberry Pi generations.

Unavailable metrics are reported as unavailable rather than treated as zero.

## Security Considerations

- Store bot credentials outside the source code.
- Restrict access through authorized Telegram chat IDs.
- Do not commit `.env` files or credentials.
- Avoid running the bot with unnecessary privileges.
- Keep Python dependencies and Raspberry Pi OS updated.
