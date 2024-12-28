import json

import openai
import requests

from settings import Settings

venice_client = openai.AsyncOpenAI(base_url=Settings.VENICE_BASE_URL, api_key=Settings.VENICE_API_KEY)

def fetch_text_models():
    venice_url = f"{Settings.VENICE_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {Settings.VENICE_API_KEY}"}
    response = requests.request("GET", venice_url, headers=headers)
    return [(model["id"], model["model_spec"]["availableContextTokens"]) for model in json.loads(response.text)["data"] if model["type"] == "text"]

async def get_chat_completion(messages, model):
    completion = await venice_client.chat.completions.create(
        messages=messages, 
        model=model
    )
    return completion.choices[0].message.content