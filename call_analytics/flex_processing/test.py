import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def main():
    try:
        with open(r"D:\Harsh\Projects-Working\SingleInterface - HyperX\call_analytics\recordings\tvs_sample_1.mp3", "rb") as audio_file:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}"
                },
                files={
                    "file": audio_file
                },
                data={
                    "model": "whisper-large-v3",
                    # Optional:
                    # "temperature": 0,
                    # "response_format": "verbose_json"
                }
            )

        print(response.json())

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()



# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# def main():
#     try:
#         response = requests.post(
#             "https://api.groq.com/openai/v1/chat/completions",
#             headers={
#                 "Content-Type": "application/json",
#                 "Authorization": f"Bearer {GROQ_API_KEY}"
#             },
#             json={
#                 "service_tier": "flex",
#                 "model": "openai/gpt-oss-120b",
#                 "messages": [{
#                     "role": "user",
#                     "content": "whats 2 + 2"
#                 }]
#             }
#         )
#         print(response.json())
#     except Exception as e:
#         print(f"Error: {str(e)}")

# if __name__ == "__main__":
#     main()
