from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

def call_hanzi_schema(hanzi: str) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()
    from hanzi_schema import HanziSchema

    response = client.responses.parse(
        model="gpt-4o",
        input=[
            {
                "role": "system",
                "content": """You are a prefessional linguist, expert in Chinese character etymology. 
                Given a Chinese character, you will analyze its origin according to the following schema: 
                mechanism (glyph_origin, semantic_extension, phonetic, other), 
                original_meaning (the original meaning of the character), 
                description (explanation of the original meaning and its evolution), 
                confidence (low, medium, high). 
                You will output the analysis in JSON format according to this schema.
                """,
            },
            {
                "role": "user",
                "content": f"""What is the origin of the Chinese character '{hanzi}'? 
                Provide your answer in JSON format according to the specified schema.""",
            },
        ],
        text_format=HanziSchema,
    )

    parsed_results = response.output_parsed
    print(parsed_results)



if __name__ == "__main__":
    call_hanzi_schema("有")
