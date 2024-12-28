import json

import httpx
import requests

from settings import Settings

def fetch_text_models():
    venice_url = f"{Settings.VENICE_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {Settings.VENICE_API_KEY}"}
    response = requests.request("GET", venice_url, headers=headers)
    return [(model["id"], model["model_spec"]["availableContextTokens"]) for model in json.loads(response.text)["data"] if model["type"] == "text"]

async def get_chat_completion(messages, model):
    timeout = httpx.Timeout(30.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{Settings.VENICE_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {Settings.VENICE_API_KEY}"}, json={"messages": messages, "model": model, "venice_parameters": {"include_venice_system_prompt": False}})
        completion = response.json()
        return completion['choices'][0]['message']['content']