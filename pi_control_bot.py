
#!/usr/bin/env python3
"""
Pi Control Bot

Remote Raspberry Pi monitoring through Telegram.

Commands:
    /start
    /ip
    /voltage
    /temp
    /status
    /fan
    /storage

Access is restricted to configured Telegram chat IDs.
"""

import os
import sys
import time
import logging
import subprocess
import ipaddress

import requests
import psutil


# --------------------------------------------------
# Configuration
# --------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

AUTHORIZED_CHAT_IDS = {
    item.strip()
    for item in os.getenv("AUTHORIZED_CHAT_IDS", "").split(",")
    if item.strip()
}

POLL_INTERVAL = 3
REQUEST_TIMEOUT = (5, 15)
TELEGRAM_MESSAGE_LIMIT = 4000

API_URL = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN else ""
)

session = requests.Session()

session.headers.update({
    "User-Agent": "PiControlBot/1.0",
})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("pi-control-bot")


# --------------------------------------------------
# Telegram API
# --------------------------------------------------

def telegram_api(method, payload=None):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Telegram token is not configured")

    response = session.post(
        f"{API_URL}/{method}",
        json=payload or {},
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result.get('description', 'Unknown error')}"
        )

    return result.get("result")


def send_message(chat_id, text, reply_markup=None):
    # Avoid exceeding Telegram's message size limit.
    text = str(text)

    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        text = text[:TELEGRAM_MESSAGE_LIMIT - 30] + "\n...[truncated]"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        telegram_api("sendMessage", payload)
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        logger.error("Failed to send Telegram message: %s", exc)


def answer_callback(callback_id):
    try:
        telegram_api(
            "answerCallbackQuery",
            {"callback_query_id": callback_id},
        )
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        logger.warning("Failed to answer callback: %s", exc)


# --------------------------------------------------
# Access control
# --------------------------------------------------

def is_authorized(chat_id):
    if not AUTHORIZED_CHAT_IDS:
        logger.error("No authorized chat IDs configured.")
        return False

    return str(chat_id) in AUTHORIZED_CHAT_IDS


# --------------------------------------------------
# Menu
# --------------------------------------------------

def build_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "📡 IP", "callback_data": "cmd_ip"},
                {"text": "🔌 Voltage", "callback_data": "cmd_voltage"},
            ],
            [
                {"text": "🌡️ Temperature", "callback_data": "cmd_temp"},
                {"text": "📊 Status", "callback_data": "cmd_status"},
            ],
            [
                {"text": "🌀 Fan RPM", "callback_data": "cmd_fan"},
                {"text": "💾 Storage", "callback_data": "cmd_storage"},
            ],
        ]
    }


# --------------------------------------------------
# Command helpers
# --------------------------------------------------

def run_command(command, timeout=5):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()

    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        OSError,
    ) as exc:
        logger.debug("Command failed (%s): %s", command[0], exc)
        return None


# --------------------------------------------------
# Raspberry Pi metrics
# --------------------------------------------------

def get_public_ip():
    services = [
        "https://ipv4.icanhazip.com",
        "https://api.ipify.org",
    ]

    for service in services:
        try:
            response = session.get(
                service,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            ip = ipaddress.ip_address(response.text.strip())

            if isinstance(ip, ipaddress.IPv4Address):
                return str(ip)

        except (
            requests.RequestException,
            ValueError,
        ):
            continue

    return "Unavailable"


def get_cpu_temp():
    output = run_command(["vcgencmd", "measure_temp"])

    if output and "temp=" in output:
        return output.split("temp=", 1)[1]

    try:
        with open(
            "/sys/class/thermal/thermal_zone0/temp",
            "r",
            encoding="utf-8",
        ) as file:
            temperature = int(file.read().strip()) / 1000

        return f"{temperature:.1f}°C"

    except (OSError, ValueError):
        return "Unavailable"


def get_voltage():
    output = run_command(["vcgencmd", "measure_volts"])

    if output and "volt=" in output:
        return output.split("volt=", 1)[1]

    return "Unavailable"


def get_cpu_ram_usage():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent

    return cpu, ram


def get_gpu_info():
    information = []

    gpu_memory = run_command([
        "vcgencmd", "get_mem", "gpu"
    ])

    if gpu_memory:
        information.append(f"GPU memory: {gpu_memory}")

    gpu_clock = run_command([
        "vcgencmd", "measure_clock", "core"
    ])

    if gpu_clock:
        information.append(f"Core clock: {gpu_clock}")

    if not information:
        return "GPU information unavailable."

    return "\n".join(information)


def get_fan_rpm():
    for path in sorted(
        __import__("glob").glob(
            "/sys/class/hwmon/hwmon*/fan*_input"
        )
    ):
        try:
            with open(path, "r", encoding="utf-8") as file:
                rpm = int(file.read().strip())

            if rpm >= 0:
                return f"{rpm} RPM"

        except (OSError, ValueError):
            continue

    return "Unavailable"


def get_disk_usage():
    output = run_command([
        "df", "-h",
        "-x", "tmpfs",
        "-x", "devtmpfs",
        "-x", "squashfs",
    ])

    return output if output else "Storage information unavailable."


# --------------------------------------------------
# Command handling
# --------------------------------------------------

def normalize_command(command):
    command = command.strip().split()[0].lower()

    if "@" in command:
        command = command.split("@", 1)[0]

    return command


def handle_command(command, chat_id):
    cmd = normalize_command(command)

    if cmd in ("/start", "menu"):
        send_message(
            chat_id,
            "🍓 Raspberry Pi Control Bot\n\n"
            "/ip - Public IP\n"
            "/voltage - Current voltage\n"
            "/temp - CPU temperature\n"
            "/status - CPU / RAM / GPU\n"
            "/fan - Fan RPM\n"
            "/storage - Disk usage",
            reply_markup=build_menu(),
        )
        return

    if cmd in ("/ip", "cmd_ip"):
        send_message(
            chat_id,
            f"🌍 Public IP: {get_public_ip()}",
        )
        return

    if cmd in ("/voltage", "cmd_voltage"):
        send_message(
            chat_id,
            f"🔌 Voltage: {get_voltage()}",
        )
        return

    if cmd in ("/temp", "cmd_temp"):
        send_message(
            chat_id,
            f"🌡️ CPU Temperature: {get_cpu_temp()}",
        )
        return

    if cmd in ("/status", "cmd_status"):
        try:
            cpu, ram = get_cpu_ram_usage()
        except Exception as exc:
            logger.error("Failed to read CPU/RAM metrics: %s", exc)
            send_message(chat_id, "Unable to retrieve system metrics.")
            return

        gpu = get_gpu_info()

        send_message(
            chat_id,
            "📊 System Status\n\n"
            f"CPU Usage: {cpu}%\n"
            f"RAM Usage: {ram}%\n\n"
            f"{gpu}",
        )
        return

    if cmd in ("/fan", "cmd_fan"):
        send_message(
            chat_id,
            f"🌀 Fan RPM: {get_fan_rpm()}",
        )
        return

    if cmd in ("/storage", "cmd_storage"):
        send_message(
            chat_id,
            f"💾 Disk Usage:\n\n{get_disk_usage()}",
        )
        return

    send_message(
        chat_id,
        "Unknown command. Use /start to see available commands.",
        reply_markup=build_menu(),
    )


# --------------------------------------------------
# Update processing
# --------------------------------------------------

def process_update(update):
    if "message" in update:
        message = update["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text")

        if chat_id is None or not text:
            return

        if not is_authorized(chat_id):
            logger.warning("Unauthorized message rejected.")
            return

        handle_command(text, chat_id)

    elif "callback_query" in update:
        callback = update["callback_query"]

        answer_callback(callback["id"])

        # Use the actual message chat, not the sender's private ID.
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        data = callback.get("data")

        if chat_id is None or not data:
            return

        if not is_authorized(chat_id):
            logger.warning("Unauthorized callback rejected.")
            return

        handle_command(data, chat_id)


# --------------------------------------------------
# Main polling loop
# --------------------------------------------------

def run_bot():
    logger.info("Starting Raspberry Pi Control Bot...")

    offset = None

    while True:
        try:
            params = {
                "timeout": 30,
                "limit": 10,
            }

            if offset is not None:
                params["offset"] = offset

            response = session.get(
                f"{API_URL}/getUpdates",
                params=params,
                timeout=(5, 40),
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                logger.error("Telegram polling returned an error.")
                time.sleep(5)
                continue

            for update in data.get("result", []):
                try:
                    process_update(update)
                except Exception:
                    logger.exception("Failed to process Telegram update")

                offset = update["update_id"] + 1

        except requests.RequestException as exc:
            logger.error("Polling network error: %s", exc)
            time.sleep(POLL_INTERVAL)

        except ValueError as exc:
            logger.error("Invalid Telegram response: %s", exc)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Bot stopped.")
            break

    session.close()


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not configured.")
        sys.exit(1)

    if not AUTHORIZED_CHAT_IDS:
        logger.error("AUTHORIZED_CHAT_IDS is not configured.")
        sys.exit(1)

    run_bot()
