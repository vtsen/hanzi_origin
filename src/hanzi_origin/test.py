from typing import Any, Optional
from dotenv import load_dotenv

from src.hanzi_origin.etymology_simple import save_to_str

load_dotenv()

def call_etymology(hanzi: str, traditional_chars: list[str]) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()
    from etymology_simple import Etymology

    prompt_for_traditional = "\n"
    if traditional_chars:
        trad_list_str = ", ".join(traditional_chars)
        prompt_for_traditional += f"""Note that the character has the following traditional forms: {trad_list_str} which may have separate etymology chains."""

    # Prepare input information
    from utils.meaning import fetch_ziyi
    initial_meaning, contemporary_meanings = fetch_ziyi(hanzi)
    input_info = f"Initial Meaning: {initial_meaning}\n\nContemporary Meanings: {contemporary_meanings}"

    response = client.responses.parse(
        model="gpt-4o",
        input=[
            {
                "role": "system",
                "content": f"""
                You are a professional linguist specializing in Chinese historical semantics and you are given two pieces of information of the character {hanzi}: \n
                1. A possible initial meaning of the character when it was created long time ago. This piece of information might be inaccurate, so be critical.\n
                2. A list of entries containing the comtemporary meanings.\n\n
                Your task is to analyze the senses of a given Chinese character and output the result strictly in JSON format according to the schema defined below.\n\n
                Note that the meaning in (1) might not correspond to any of the meanings in (2), in which case you should make a separate entry of sense for it; otherwise, merge it to the corresponding sense in (2).\n\n
                GENERAL PRINCIPLES:\n
                - Do NOT invent speculative senses. Stick to what is given.\n
                - Treat each distinct meaning (sense) as a separate node.\n
                - No extra, no missing.\n
                - Use modern linguistic analysis, but ground all claims in attested or widely accepted historical usage.\n
                SCHEMA DESCRIPTION:\n\n
                The output JSON must contain a single object with the following top-level fields:\n\n
                \"senses\": an array of sense objects. Each sense object represents one distinct meaning.\n\n
                Each sense object MUST have:\n
                - \"index\": integer. A unique identifier for this sense. Indices must be stable and used consistently in edges.\n
                - \"part_of_speech\": string. Examples: \"noun\", \"verb\", \"adjective\", \"function word\", etc.\n
                - \"meaning\": string. A concise definition of the sense.\n
                - \"examples\": array of strings. Classical or modern examples illustrating this sense. May be empty if examples are unavailable.\n\n
                - \"traditional_chars\": array of strings. Corresponding traditional characters for this sense, if any. May be empty.\n\n
                IMPORTANT CONSTRAINTS:\n
                - Output MUST be valid JSON. No comments, no trailing commas.\n
                - Do NOT include any text outside the JSON object.\n
                - All values of "meaning" MUST be written in Chinese.\n
                - All strings in "examples" MUST be written in Chinese (Classical or Modern).\n

                You will be given ONE Chinese character as input. Produce exactly ONE JSON object following the schema above.
                """
            },
            {
                "role": "user",
                "content": f"""What are the senses of the Chinese character '{hanzi}'? {prompt_for_traditional}\n
                Provide your answer in JSON format according to the specified schema.\n\n
                Below are the initial meaning and contemporary meanings:\n{input_info}""",
            },
        ],
        text_format=Etymology,
    )

    parsed_results = response.output_parsed
    print(save_to_str(parsed_results))



if __name__ == "__main__":
    call_etymology("面", ["面", "麵"])
