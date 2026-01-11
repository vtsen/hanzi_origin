import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Create client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def main():
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input="Say hello in Chinese."
        )

        # The high-level parsed content is available under response.output_text
        print("Model output:")
        print(response.output_text)

    except Exception as e:
        print(f"[ERROR] API call failed: {e}")

if __name__ == "__main__":
    main()
