from typing import Any, Optional
from dotenv import load_dotenv
from pathlib import Path

from src.hanzi_origin.etymology import save_to_str

load_dotenv()

def call_etymology(
    hanzi: str,
    traditional_chars: list[str],
    initial_meaning: str,
    contemporary_meanings: str,
    model: str = "gpt-4o-mini",
) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()
    from etymology import Etymology

    prompt_for_traditional = "\n"
    if traditional_chars:
        trad_list_str = ", ".join(traditional_chars)
        prompt_for_traditional += f"""Note that the character additionally has the following traditional forms: {trad_list_str} which may have separate etymology chains."""

    input_info = f"Initial Meaning: {initial_meaning}\n\nContemporary Meanings: {contemporary_meanings}"

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": """
                You are a professional linguist specializing in Chinese historical semantics and etymology, and you are given two pieces of information of the given character: \n
                1. A possible initial meaning of the character when it was created long time ago. This piece of information might be inaccurate, so be critical.\n
                2. A list of entries containing the comtemporary meanings.\n\n
                Your task is to analyze the senses, original formation, and etymology of a given Chinese character and output the result strictly in JSON format according to the schema defined below.\n\n
                GENERAL PRINCIPLES:\n
                - Do NOT invent speculative senses. Stick to what is given.\n
                - Treat each distinct meaning (sense) as a separate node.\n
                - For sense extraction: no extra, no missing.\n
                - The initial meaning typically corresponds an item in the contemporary meaning list, if so, do not separately list. Otherwise, if it does not correspond to any of the meanings in (2), then make a separate entry of sense for it.\n\n
                - If there is only one sense (rare), edge list should be empty.\n
                - Use modern linguistic analysis, but ground all claims in attested or widely accepted historical usage.\n
                - If a relationship between two senses is uncertain, you are encouraged to mark its evolution_type as UNKNOWN.\n
                - All senses with the same traditional_char should be either directly or indirectly connected. Make sure you do not leave out senses in the graph, nor hallucinate fake linkage.\n
                - The etymology structure is a directed acyclic graph (DAG), but disconnected components are allowed.\n\n
                SCHEMA DESCRIPTION:\n\n
                The output JSON must contain a single object with the following top-level fields:\n\n
                1. \"senses\": an array of sense objects. Each sense object represents one distinct meaning.\n\n
                Each sense object MUST have:\n
                - \"index\": integer. A unique identifier for this sense. Indices must be stable and used consistently in edges.\n
                - \"part_of_speech\": string. Must be one of the predefined PartOfSpeech enum values, e.g.: \"noun\", \"verb\", \"adjective\", \"measure_word\", etc.\n
                - \"meaning\": string. A concise definition of the sense.\n
                - \"examples\": array of strings. Classical or modern examples illustrating this sense. May be empty if examples are unavailable.\n\n
                - \"traditional_char\": string. The corresponding traditional character for this sense, which could be the same as simplified. Think carefully to pick.\n\n
                2. \"formations\": an array of CharacterFormation objects. Each formation object represents the formation of one distinct traditional charactor.\n\n
                Each formation object MUST have:\n
                - "formation_type": string. The character formation method, based on the Six Principles (六书) as revised by modern linguistics. Must be one of the predefined formation type enum values (e.g. pictograph, phono_semantic_compound, loan_character, etc.).
                - "original_sense_index": integer. The index of the sense that represents the original meaning at the time of character creation. This value must correspond to exactly one sense index defined in the senses array.
                - "note": string. Explanatory notes on the character’s formation, such as component analysis, historical evidence, or scholarly uncertainty.. Keep it short but cannot be empty!\n
                3. \"edges\": an array of etymology edge objects. Each edge represents a directional semantic or grammatical development between two senses.\n\n
                Each edge object MUST have:\n
                - \"source_index\": integer. The index of the earlier or source sense.\n
                - \"target_index\": integer. The index of the derived or later sense.\n
                - \"evolution_type\": string. Must be ONE of the following values:\n  - \"semantic_extension\"\n  - \"semantic_narrowing\"\n  - \"semantic_shift\"\n  - \"metaphor\"\n  - \"metonymy\"\n  - \"synecdoche\"\n  - \"pejoration\"\n  - \"amelioration\"\n  - \"grammaticalization\"\n  - \"function_word\"\n  - \"conversion\"\n  - \"loan_shift\"\n  - \"analogy\"\n  - \"reanalysis\"\n  - \"unknown\"\n
                - \"note\": string. Clarification such as historical period, mechanism explanation, or scholarly uncertainty. Keep it short but cannot be empty!\n\n
                IMPORTANT CONSTRAINTS:\n
                - Output MUST be valid JSON. No comments, no trailing commas.\n
                - Do NOT include any text outside the JSON object.\n
                - Index of senses must start from 0 and are consecutive integers.\n
                - If there are multiple traditional chars among the senses you extracted, each should correspond to one and only one formation in the formations list!\n
                - Prefer metaphor / metonymy / synecdoche when a clear mechanism exists; use semantic_shift only when no specific mechanism can be confidently identified.\n
                - All values of "meaning" MUST be written in Chinese.\n
                - All strings in "examples" MUST be written in Chinese (Classical or Modern).\n
                
                - ALL senses with the same traditional_char MUST be either directly or indirectly connected. Make sure you do not leave out senses in the edges!\n
                - ALL senses with the same traditional_char MUST be either directly or indirectly connected. Make sure you do not leave out senses in the edges!\n
                - ALL senses with the same traditional_char MUST be either directly or indirectly connected. Make sure you do not leave out senses in the edges!\n
                
                - If a relationship between two senses is uncertain, you are encouraged to mark its evolution_type as UNKNOWN.\n
                
                You will be given ONE Chinese character as input. Produce exactly ONE JSON object following the schema above.
                """
            },
            {
                "role": "user",
                "content": f"""What are the senses and the etymology of the Chinese character '{hanzi}'? {prompt_for_traditional}\n
                Provide your answer in JSON format according to the specified schema.
                Below are the initial meaning and contemporary meanings:\n{input_info}""",
            },
        ],
        text_format=Etymology,
    )

    parsed_results = response.output_parsed
    return parsed_results


def call_dep_enricher(
        input_filename: Path,
        hanzi: str,
        model: str = "gpt-4o-mini",
) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()
    from etymology import load_from_file, Dependencies

    instance = load_from_file(input_filename)

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": """
                You are a professional linguist specializing in Chinese historical semantics and etymology, and you are given the description of the ogic of initial formation of the character. \n
                Find the dependent Hanzi characters that the target character was originally formed from.\n
                Do NOT include: \n
                - The target character itself\n
                - Explanations\n
                Crucial note: \n
                - If a radical is not a common independent characters, use its contemporary conterparty, e.g. '草' instead of '艹', '人' instead of '亻' or '彳'.\n  
                - It is completely possible that no dependency exists (e.g. pure pictograph, unknown origin, etc.), in which case return an EMPTY list.
                SCHEMA DESCRIPTION:\n\n
                The output JSON must contain only a single array of strings. Each string object in the list represents one distinct charactor it depends on and must be a single charactor.\n\n
                
                You will be given ONE Chinese character as input. Produce exactly ONE JSON object following the schema above.
                """
            },
            {
                "role": "user",
                "content": f"""What are the upstream dependency of the Chinese character '{hanzi}'?\n
                Provide your answer in JSON format according to the specified schema.
                Below are the initial meaning and logic of formation:\n{instance.formations}""",
            },
        ],
        text_format=Dependencies,
    )

    parsed_results = response.output_parsed
    return parsed_results


def run_etymology():
    # hanzi, traditional_chars = "面", ["面", "麵"]
    hanzi, traditional_chars = "人", []
    # hanzi, traditional_chars = "国", ["國"]
    # hanzi, traditional_chars = "我", []

    # Prepare input information
    from utils.meaning import fetch_ziyi
    initial_meaning, contemporary_meanings = fetch_ziyi(hanzi)

    results = call_etymology(hanzi, traditional_chars, initial_meaning, contemporary_meanings)
    print(save_to_str(results))


def run_enricher():
    task_name = "chars"
    project_root = Path(__file__).resolve().parent.parent.parent

    hanzi, json_idx = "茶", 1411
    hanzi, json_idx = "刷", 1310
    hanzi, json_idx = "绊", 1346
    hanzi, json_idx = "钙", 1525
    hanzi, json_idx = "乏", "0147"
    hanzi, json_idx = "车", "0100"
    # hanzi, json_idx = "肃", 1303
    # hanzi, json_idx = "隶", 1305

    json_dir = project_root / "data" / "etymology" / f"etymology_for_{task_name}" / f"{json_idx}.json"
    results = call_dep_enricher(json_dir, hanzi, model="gpt-4o")
    print(results)


if __name__ == "__main__":
    run_enricher()
