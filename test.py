api_key = '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'

import openai
from dotenv import load_dotenv
import os

secret_key = os.getenv('OPENAI_API_KEY')

load_dotenv()

client = openai.OpenAI(api_key=api_key)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "explain taghazout!"}]
)

# Réponse du modèle
answer = response.choices[0].message.content.strip()

print(answer)