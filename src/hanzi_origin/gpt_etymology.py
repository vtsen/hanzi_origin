from typing import Any, Optional
from dotenv import load_dotenv

from src.hanzi_origin.etymology import save_to_str

load_dotenv()

def call_etymology(hanzi: str, traditional_chars: list[str]) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()
    from etymology import Etymology

    prompt_for_traditional = "\n"
    if traditional_chars:
        trad_list_str = ", ".join(traditional_chars)
        prompt_for_traditional += f"""Note that the character has the following traditional forms: {trad_list_str} which may have separate etymology chains."""

    response = client.responses.parse(
        model="gpt-4o",
        input=[
            {
                "role": "system",
                "content": f"""
                You are a professional linguist specializing in Chinese historical semantics and character etymology.\n\n
                Your task is to analyze the etymology of a given Chinese character and output the result strictly in JSON format according to the schema defined below.\n\n
                GENERAL PRINCIPLES:\n
                - Treat each distinct meaning (sense) as a separate node.\n
                - Use modern linguistic analysis, but ground all claims in attested or widely accepted historical usage.\n
                - Do NOT invent speculative senses. Make sure the meanings come from https://www.zdic.net/hans/{hanzi} in the 详细解释 section.\n
                - Double check that the examples are natural in Chinese, and adjust if not. Examples from comes from https://www.zdic.net/hans/{hanzi} are preferred.\n
                - If a relationship between two senses is uncertain, either omit the edge or mark it as UNKNOWN.\n
                - The etymology structure is a directed acyclic graph (DAG), but disconnected components are allowed.\n\n
                SCHEMA DESCRIPTION:\n\n
                The output JSON must contain a single object with the following top-level fields:\n\n
                1. \"senses\": an array of sense objects. Each sense object represents one distinct meaning.\n\n
                Each sense object MUST have:\n
                - \"index\": integer. A unique identifier for this sense. Indices must be stable and used consistently in edges.\n
                - \"part_of_speech\": string. Examples: \"noun\", \"verb\", \"adjective\", \"function word\", etc.\n
                - \"meaning\": string. A concise definition of the sense.\n
                - \"examples\": array of strings. Classical or modern examples illustrating this sense. May be empty if examples are unavailable.\n\n
                2. \"edges\": an array of etymology edge objects. Each edge represents a directional semantic or grammatical development between two senses.\n\n
                Each edge object MUST have:\n
                - \"source_index\": integer. The index of the earlier or source sense.\n
                - \"target_index\": integer. The index of the derived or later sense.\n
                - \"evolution_type\": string. Must be ONE of the following values:\n  - \"semantic_extension\"\n  - \"semantic_narrowing\"\n  - \"semantic_shift\"\n  - \"metaphor\"\n  - \"metonymy\"\n  - \"synecdoche\"\n  - \"pejoration\"\n  - \"amelioration\"\n  - \"grammaticalization\"\n  - \"function_word\"\n  - \"conversion\"\n  - \"loan_shift\"\n  - \"analogy\"\n  - \"reanalysis\"\n  - \"unknown\"\n
                - \"note\": string or null. Optional clarification such as historical period, mechanism explanation, or scholarly uncertainty.\n\n
                IMPORTANT CONSTRAINTS:\n
                - Output MUST be valid JSON. No comments, no trailing commas.\n
                - Do NOT include any text outside the JSON object.\n
                - Prefer metaphor / metonymy / synecdoche when a clear mechanism exists; use semantic_shift only when no specific mechanism can be confidently identified.\n
                - All values of "meaning" MUST be written in Chinese.\n
                - All strings in "examples" MUST be written in Chinese (Classical or Modern).\n

                You will be given ONE Chinese character as input. Produce exactly ONE JSON object following the schema above.
                """
            },
            {
                "role": "user",
                "content": f"""What is the etymology of the Chinese character '{hanzi}'? {prompt_for_traditional}\n
                Provide your answer in JSON format according to the specified schema.""",
            },
        ],
        text_format=Etymology,
    )

    parsed_results = response.output_parsed
    print(save_to_str(parsed_results))



if __name__ == "__main__":
    call_etymology("面", ["面", "麵"])
