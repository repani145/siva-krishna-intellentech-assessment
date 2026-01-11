from ai_engine import AI_AGENT
from utils import actions_items_parser
from datetime import datetime
import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Input data files path
transcript_file_path = "input_data/sprint_planning.txt"
people_file_path="input_data/people.json"

if __name__ == "__main__":
    client = Groq(api_key=GROQ_API_KEY)
    try:
        agent = AI_AGENT(
            transcript_file_path=transcript_file_path,
            people_file_path=people_file_path,
            client = client
        )
        result = agent.start_process()

        # for output file
        os.makedirs("outputs", exist_ok=True)
        transcript = result["meeting_type"]
        base_date = datetime.now()
        timestamp = base_date.strftime("%Y_%m_%d")
        output_file_path = f"outputs/{transcript}_{timestamp}.json"
        
        final_result = actions_items_parser(result, base_date)

        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)

        # print(json.dumps(final_result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(e)