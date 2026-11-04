import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")
model = os.getenv("LLM_MODEL")

print("API Key loaded:", bool(api_key))
print("Base URL:", base_url)
print("Model:", model)

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: Groq is working"
            }
        ],
        temperature=0
    )

    print("\nSUCCESS ✅")
    print(response.choices[0].message.content)

except Exception as e:
    print("\nFAILED ❌")
    print(type(e).__name__)
    print(str(e))