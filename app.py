import re
import os
import dotenv
import aiohttp
import asyncio
from googleapiclient.discovery import build
from groq import Groq
from quart import Quart, render_template, send_from_directory, request, jsonify
import google.generativeai as genai

app = Quart(__name__)


@app.route("/")
async def index():
    return await render_template("index.html")


@app.route("/search", methods=["POST"])
async def search():
    form = await request.form
    query = form.get("query")
    crawler = Lyrics_Crawler()
    response = crawler.search(query)
    links = extract_hyperlinks(response)
    usable_links = return_usable_links(links)
    link_index = 0
    scrape = await scrape_link(usable_links[link_index])
    lyrics = crawler.extract_lyrics(scrape)
    while True:
        if "Error: 371" in lyrics:
            link_index += 1
            scrape = await scrape_link(usable_links[link_index])
            lyrics = crawler.extract_lyrics(scrape)
        else:
            break
    summary = crawler.summarize_lyrics(lyrics)
    color_description = crawler.choose_colors(lyrics, summary)
    color_input = crawler.pick_color(color_description)
    hex_codes = extract_hex_codes(color_input)
    return jsonify({
        "lyrics": lyrics,
        "summary": summary,
        "color1": hex_codes[0],
        "color2": hex_codes[1],
        "color3": hex_codes[2],
    })


model_map = {
    "Distil-Whisper English": "distil-whisper-large-v3-en",
    "Gemma 2 9B": "gemma-2-9b-it",
    "Gemma 7B": "gemma-7b-it",
    "Llama 3 70B Tool Use (Preview)": "llama3-groq-70b-8192-tool-use-preview",
    "Llama 3 70B Versatile": "llama-3.1-70b-versatile",
    "Mixtral 8x7B": "mixtral-8x7b-32769",
}


def extract_hex_codes(input_text):
    # Regular expression pattern to match hex codes
    pattern = r"#[0-9A-Fa-f]{6}"

    # Find all matches in the input text
    matches = re.findall(pattern, input_text)

    # Return the first three matches, or fewer if there are less than three
    return matches[:3]


class Lyrics_Crawler:
    def __init__(self):
        with open("sysprompt_extract.txt", "r") as f:
            self.system_prompt = f.read()
        dotenv.load_dotenv()
        self.google_api_key = os.getenv("GOOGLE_CSE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=self.groq_api_key)
        self.model = model_map["Llama 3 70B Versatile"]
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=self.gemini_api_key)

        with open("sysprompt_summary.txt", "r") as f:
            self.sysprompt_summary = f.read()
        with open("sysprompt_color.txt", "r") as f:
            self.sysprompt_color = f.read()
        with open("sysprompt_pick_color.txt", "r") as f:
            self.sysprompt_color_pick = f.read()

    def search(self, search_term):
        search_term = search_term + " lyrics"
        service = build("customsearch", "v1", developerKey=self.google_api_key)
        res = service.cse().list(q=search_term, cx=self.google_cse_id).execute()
        return res

    def extract_lyrics(self, markdown):
        message = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": markdown},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=message,
            max_tokens=8000,
            stop=None,
            temperature=0.5,
            top_p=1,
        )
        return response.choices[0].message.content

    def summarize_lyrics(self, lyrics):
        summary_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", system_instruction=self.sysprompt_summary
        )
        summary = summary_model.generate_content(lyrics)
        return summary.text

    def pick_color(self, color_description):
        color_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", system_instruction=self.sysprompt_color_pick
        )
        color_input = color_model.generate_content(color_description)
        return color_input.text

    def choose_colors(self, lyrics, summary):
        color_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", system_instruction=self.sysprompt_color
        )
        lyrics_and_summary = lyrics + summary
        color_input = color_model.generate_content(lyrics_and_summary)
        return color_input.text


async def scrape_link(url):
    try:
        jina_url = "https://r.jina.ai/" + url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(jina_url, headers=headers) as response:
                response.raise_for_status()
                print(f"Successfully fetched {jina_url}")
                return await response.text()
    except aiohttp.ClientError as e:
        print(f"Client error occurred while fetching {jina_url}: {e}")
        return None
    except asyncio.TimeoutError:
        print(f"Request timed out for {jina_url}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching {jina_url}: {e}")
        return None


def extract_hyperlinks(cse_response):
    items = cse_response.get("items", [])
    links = [item["link"] for item in items if "link" in item]
    return links


def return_usable_links(links):
    usable_links = []
    for link in links:
        if "youtube" in link.lower():
            continue
        else:
            usable_links.append(link)
    return usable_links


async def main():
    crawler = Lyrics_Crawler()
    response = crawler.search("terminal kolja")
    links = extract_hyperlinks(response)
    usable_links = return_usable_links(links)
    link_index = 0
    scrape = await scrape_link(usable_links[link_index])
    lyrics = crawler.extract_lyrics(scrape)
    while True:
        if "Error: 371" in lyrics:
            link_index += 1
            scrape = await scrape_link(usable_links[link_index])
            lyrics = crawler.extract_lyrics(scrape)
        else:
            break
    print(lyrics)


if __name__ == "__main__":    
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 for local testing
    app.run(host="0.0.0.0", port=port)
