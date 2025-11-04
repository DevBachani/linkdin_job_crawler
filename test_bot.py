import requests

BOT_TOKEN="8416984310:AAGLcgCvPm18yWSXiRSNKNihZEIvcFzEfVo"
CHAT_ID="6611176305"
msg = "🚀 Bot connected successfully!"

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": msg}
)
