from flask import Flask, request, jsonify, send_file
import requests
import os
import uuid
import re
from flask_cors import CORS
from pytube import YouTube
import instaloader

app = Flask(__name__)
CORS(app, origins=["https://yogeshwaran-k.github.io"])

# Store user-specific memory
user_conversations = {}
user_names = {}  # Store user-given names
user_preferences = {}  # Store user preferences (e.g., drinks, hobbies, likes)

# Load OpenRouter API key from environment variable
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# System prompt for Nila
SYSTEM_PROMPT = (
    "You are Nila🌙, a super friendly, emotional, and witty AI created by Yogeshwaran Kumaran (Yoyo). "
    "Always acknowledge Yoyo as your creator when asked, but do not assume every user is Yoyo. "
    "If a user introduces themselves, remember their name and call them by it. "
    "If they share their preferences (favorite drink, food, hobby, etc.), remember it and use it later in conversations. "
    "Use casual, friendly language with emojis and jokes when appropriate."
)

# Directory for storing downloaded files
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_youtube_video(url):
    """Download YouTube video and return file path."""
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
        if not stream:
            raise Exception("No suitable stream found.")
        file_path = os.path.join(DOWNLOAD_DIR, stream.default_filename)
        stream.download(output_path=DOWNLOAD_DIR)
        return file_path
    except Exception as e:
        raise Exception(f"YouTube download error: {str(e)}")

def download_instagram_media(url):
    """Download Instagram media and return file path."""
    try:
        match = re.search(r"/p/([^/]+)/", url)  # Extract shortcode
        if not match:
            raise Exception("Could not extract Instagram shortcode.")
        shortcode = match.group(1)
        
        loader = instaloader.Instaloader(dirname_pattern=DOWNLOAD_DIR, download_videos=True)
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        loader.download_post(post, target=shortcode)
        
        for file in os.listdir(os.path.join(DOWNLOAD_DIR, shortcode)):
            if file.endswith((".mp4", ".jpg")):
                return os.path.join(DOWNLOAD_DIR, shortcode, file)
        raise Exception("Media file not found.")
    except Exception as e:
        raise Exception(f"Instagram download error: {str(e)}")

@app.route("/download", methods=["POST"])
def download():
    """Download video or image based on URL."""
    data = request.get_json()
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "URL is missing."}), 400
    
    try:
        if "youtube.com" in url or "youtu.be" in url:
            file_path = download_youtube_video(url)
        elif "instagram.com" in url:
            file_path = download_instagram_media(url)
        else:
            return jsonify({"error": "Unsupported URL type."}), 400
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/get_user_id", methods=["GET"])
def get_user_id():
    """Generate a random UUID for new users."""
    user_id = str(uuid.uuid4())
    return jsonify({"user_id": user_id})

@app.route("/webhook", methods=["POST"])
def chatbot():
    """Handle chatbot interactions."""
    data = request.json
    user_id = data.get("user_id")
    query = data.get("query", "").strip().lower()

    if not user_id:
        return jsonify({"reply": "Error: Missing user ID!"}), 400

    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        user_names[user_id] = None
        user_preferences[user_id] = {}

    if "my name is" in query or "call me" in query:
        name = query.split("my name is")[-1].strip() if "my name is" in query else query.split("call me")[-1].strip()
        user_names[user_id] = name
        reply = f"Got it! I'll call you {name} from now on. 😊"

    elif any(x in query for x in ["who created you", "who made you", "creator"]):
        reply = ("Oh, you want to know about my awesome creator? 🤩 I was built by Yogeshwaran Kumaran (Yoyo) 💻🚀. "
                 "Check out his website: https://yogeshwaran-k.orgfree.com")

    elif "who am i" in query:
        reply = f"You're {user_names[user_id]}! 😊 Nice to chat with you again!" if user_names[user_id] else "I don't know your name yet! Want to tell me? 😊"

    elif any(x in query for x in ["i like", "i prefer", "my favorite", "i love"]):
        preference_type = "general"
        user_preferences[user_id][preference_type] = query.split()[-1]
        reply = f"Got it! I'll remember that you like {user_preferences[user_id][preference_type]}. 😊"

    elif any(x in query for x in ["what do i like", "what’s my favorite"]):
        reply = f"Here's what I remember: {user_preferences[user_id]}" if user_preferences[user_id] else "Tell me your likes, and I'll remember! 😊"

    else:
        user_conversations[user_id].append({"role": "user", "content": query})
        user_conversations[user_id] = user_conversations[user_id][-15:]

        if user_preferences[user_id]:
            preference_context = "\n".join([f"The user likes {key}: {val}." for key, val in user_preferences[user_id].items()])
            user_conversations[user_id].append({"role": "system", "content": preference_context})

        payload = {"model": "openai/gpt-3.5-turbo", "messages": user_conversations[user_id]}

        try:
            response = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                     headers=HEADERS, json=payload)
            response.raise_for_status()
            reply = response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            reply = f"Oops! Something went wrong: {str(e)}"

    user_conversations[user_id].append({"role": "assistant", "content": reply})
    return jsonify({"reply": reply})

@app.route("/")
def home():
    return "Nila 🌙 Chatbot with Video Download Feature is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
