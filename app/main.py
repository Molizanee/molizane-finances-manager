import os
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from .graph.finance_graph import start_graph_by_user_message
from . import database  # Import to create tables

load_dotenv()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

app = FastAPI(
    title="Personal Finances Agent",
    description="An API for managing personal finances with LangChain & LangGraph",
    version="0.0.1",
)

database.create_tables()


@app.on_event("startup")
async def setup_telegram_webhook():
    server_endpoint = os.getenv("SERVER_ENDPOINT")
    telegram_webhook_register_url = f"https://api.telegram.org/bot{bot_token}/setWebhook?url={server_endpoint}/api/v1/webhook/telegram"
    async with httpx.AsyncClient() as client:
        try:
            result = await client.post(telegram_webhook_register_url)
            print(
                f"Telegram webhook setup status: {result.status_code} - message: {result.text}"
            )
        except httpx.ConnectError as e:
            print(f"Failed to connect to Telegram API: {e}")
        except Exception as e:
            print(f"Error setting up Telegram webhook: {e}")


class TelegramChat(BaseModel):
    id: int

    class Config:
        extra = "ignore"


class TelegramMessage(BaseModel):
    text: Optional[str] = None
    chat: TelegramChat

    class Config:
        extra = "ignore"


class NewTelegramMessage(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None

    class Config:
        extra = "ignore"


@app.post("/api/v1/webhook/telegram")
async def incoming_telegram_message(body: NewTelegramMessage):
    print(body)
    if body.message and body.message.text:
        text = body.message.text
        chat_id = body.message.chat.id

        ai_answer = start_graph_by_user_message(f"chat_id: {chat_id}\n{text}")

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": ai_answer},
            )

        print(f"Received message: {text} from chat {chat_id}")
    else:
        print("Received non-message update")
