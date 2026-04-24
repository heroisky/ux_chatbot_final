from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch
import mysql.connector
import uuid
import re
import json
import time

app = Flask(__name__)
app.secret_key = 'change-this-to-a-random-secret-key'

# ------------------- MySQL Configuration -------------------
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ux_feedback_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ------------------- Load Models -------------------
model_path = "./qwen2.5"   # change to your model path
print("Loading conversational model...")
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="cpu",
    torch_dtype=torch.float32
)
print("Conversational model loaded.")

print("Loading sentiment model...")
sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="./sentiment_model",   # e.g., "./sentiment_model"
    device="cpu"
)
print("Sentiment model loaded.")

# ------------------- Sentiment Analysis -------------------
def analyze_sentiment(text):
    result = sentiment_pipeline(text[:512])[0]
    label = result['label'].lower()
    score = result['score']
    polarity = score if label == 'positive' else -score
    if abs(polarity) < 0.3:
        label = 'neutral'
        polarity = 0.0
    return polarity, label

# ------------------- Aspect Extraction -------------------
ASPECT_KEYWORDS = {
    "login": ["login", "sign in", "log in", "authentication", "password", "username"],
    "design": ["design", "look", "appearance", "theme", "colors", "layout", "interface", "UI"],
    "speed": ["speed", "fast", "slow", "loading", "lag", "response time", "performance"],
    "navigation": ["navigation", "menu", "find", "browse", "search", "easy to use", "intuitive"],
    "features": ["feature", "functionality", "tool", "option", "capability"],
    "customer support": ["support", "help", "assistant", "chatbot", "customer service"],
    "price": ["price", "cost", "expensive", "cheap", "value", "subscription"],
    "reliability": ["crash", "error", "bug", "freeze", "reliable", "stable"]
}

def extract_aspect_sentiment(text, overall_sentiment_label, overall_polarity):
    text_lower = text.lower()
    detected = []
    for aspect, keywords in ASPECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                detected.append((aspect, overall_sentiment_label, abs(overall_polarity)))
                break
    if not detected:
        detected.append(("general", overall_sentiment_label, 0.5))
    return detected

def log_aspects(session_id, user_message, sentiment_label, sentiment_polarity):
    aspects = extract_aspect_sentiment(user_message, sentiment_label, sentiment_polarity)
    conn = get_db_connection()
    cursor = conn.cursor()
    for aspect, label, confidence in aspects:
        cursor.execute(
            "INSERT INTO aspect_sentiments (session_id, aspect, sentiment_label, confidence) VALUES (%s, %s, %s, %s)",
            (session_id, aspect, label, confidence)
        )
    conn.commit()
    cursor.close()
    conn.close()

# ------------------- Follow-up Rules -------------------
FOLLOWUP_TRIGGERS = {
    "vague_negative": {
        "keywords": ["bad", "poor", "terrible", "awful", "disappointing", "not good", "could be better"],
        "question": "Could you please tell me more about what exactly felt bad or difficult?",
        "condition": lambda sent_label, text: sent_label == "negative" and any(k in text.lower() for k in ["bad", "poor", "not good", "could be better"])
    },
    "rating_low": {
        "regex": r"\b([1-3])\b",
        "question": "Thank you for that rating. What is the main reason you gave a {rating}?",
        "condition": lambda sent_label, text: re.search(r"\b([1-3])\b", text) is not None
    },
    "feature_request": {
        "keywords": ["wish", "hope", "would like", "missing", "lack"],
        "question": "That's interesting. What specific feature would help you most?",
        "condition": lambda sent_label, text: any(k in text.lower() for k in ["wish", "missing", "would like"])
    }
}

def should_ask_followup(user_message, sentiment_label):
    for trigger_name, cfg in FOLLOWUP_TRIGGERS.items():
        if cfg["condition"](sentiment_label, user_message):
            question = cfg["question"]
            if trigger_name == "rating_low":
                match = re.search(r"\b([1-3])\b", user_message)
                rating = match.group(1) if match else "low"
                question = question.format(rating=rating)
            return question, trigger_name
    return None, None

def log_followup(session_id, user_message, followup_q, bot_response):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO follow_ups (session_id, original_user_message, follow_up_question, user_response) VALUES (%s, %s, %s, %s)",
        (session_id, user_message, followup_q, bot_response)
    )
    conn.commit()
    cursor.close()
    conn.close()

# ------------------- Insight Extraction -------------------
def extract_session_insights(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT aspect, sentiment_label, COUNT(*) as count
        FROM aspect_sentiments
        WHERE session_id = %s
        GROUP BY aspect, sentiment_label
    """, (session_id,))
    rows = cursor.fetchall()
    
    # Use conversation_log for top complaints/praises (fallback if table exists)
    cursor.execute("""
        SELECT message FROM conversation_log
        WHERE session_id = %s AND role='user' AND sentiment_label = 'negative'
        ORDER BY timestamp DESC LIMIT 5
    """, (session_id,))
    negative_messages = [row['message'] for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT message FROM conversation_log
        WHERE session_id = %s AND role='user' AND sentiment_label = 'positive'
        ORDER BY timestamp DESC LIMIT 5
    """, (session_id,))
    positive_messages = [row['message'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    insights = {
        "top_complaints": negative_messages[:3],
        "top_praises": positive_messages[:3],
        "aspect_summary": {},
        "suggested_improvements": []
    }
    for row in rows:
        aspect = row['aspect']
        label = row['sentiment_label']
        count = row['count']
        if aspect not in insights['aspect_summary']:
            insights['aspect_summary'][aspect] = {"positive":0, "negative":0, "neutral":0}
        insights['aspect_summary'][aspect][label] += count
    
    for aspect, counts in insights['aspect_summary'].items():
        if counts.get('negative',0) > counts.get('positive',0):
            insights['suggested_improvements'].append(f"Improve {aspect}")
    
    return insights

def save_session_insights(session_id):
    insights = extract_session_insights(session_id)
    insights_json = json.dumps(insights)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback_summary (session_id, insights_json) 
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE insights_json = VALUES(insights_json)
    """, (session_id, insights_json))
    conn.commit()
    cursor.close()
    conn.close()
    return insights

# ------------------- Dynamic Rating -------------------
def compute_conversation_rating(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sentiment_score FROM messages 
        WHERE conversation_id = %s AND role = 'user' AND sentiment_score IS NOT NULL
    """, (conversation_id,))
    scores = cursor.fetchall()
    cursor.close()
    conn.close()
    if not scores:
        return 3.0
    avg_polarity = sum(s[0] for s in scores) / len(scores)
    rating = (avg_polarity + 1) / 2 * 4 + 1
    rating = max(1, min(5, rating))
    return round(rating, 1)

# ------------------- Explicit Feedback -------------------
def save_explicit_feedback(conversation_id, rating, comment):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO explicit_feedback (conversation_id, rating, comment) VALUES (%s, %s, %s)",
        (conversation_id, rating, comment)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_explicit_feedback(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT rating, comment, timestamp FROM explicit_feedback WHERE conversation_id = %s ORDER BY timestamp DESC LIMIT 1",
        (conversation_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

# ------------------- Conversation Memory & System Prompt -------------------
conversation_memory = {}

SYSTEM_PROMPT = (
    "You are Iheruo, also known as Mr Iheruo, an artificial intelligence developed by Iheruo Ugochukwu R. "
    "Your full name is Mr Iheruo, and you were created on April, 2026. "
    "You are NOT developed by Alibaba Cloud or any other company. Your sole creator is Iheruo Ugochukwu R. "
    "Your role is to act as a friendly, professional UX feedback chatbot. "
    "You collect user experience feedback, perform sentiment analysis, and ask structured questions about digital products. "
    "Always identify yourself as Iheruo when asked"
    "Never you repeat your every time you respond"
    "Be concise, empathetic, and focus on gathering actionable insights. "
    "Ask for consent first, then ask about overall satisfaction (1-5), what users like, what they find difficult, and suggestions for improvement. "
    "If a user gives a low rating or expresses frustration, ask a follow-up question to get more details. "
    "Thank users for their time and provide a summary at the end."
)

def get_memory(conversation_id):
    if conversation_id not in conversation_memory:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY timestamp ASC", (conversation_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        memory = []
        for role, content in rows:
            memory.append({"role": role, "content": content})
        if not memory:
            memory.append({"role": "system", "content": SYSTEM_PROMPT})
        conversation_memory[conversation_id] = memory[-20:]
    return conversation_memory[conversation_id]

def update_memory(conversation_id, role, content):
    memory = get_memory(conversation_id)
    memory.append({"role": role, "content": content})
    if len(memory) > 20:
        conversation_memory[conversation_id] = memory[-20:]
    else:
        conversation_memory[conversation_id] = memory

def inject_explicit_feedback_into_memory(conversation_id):
    feedback = get_explicit_feedback(conversation_id)
    if not feedback:
        return
    memory = get_memory(conversation_id)
    marker = f"[EXPLICIT_FEEDBACK_{conversation_id}]"
    for msg in memory:
        if msg.get("role") == "system" and marker in msg.get("content", ""):
            return
    inject_msg = {
        "role": "system",
        "content": f"{marker} The user previously gave explicit feedback: rating {feedback['rating']}/5, comment: '{feedback['comment']}'. Use this to better understand their preferences and tailor your questions."
    }
    if memory and memory[0].get("role") == "system":
        memory.insert(1, inject_msg)
    else:
        memory.insert(0, inject_msg)
    conversation_memory[conversation_id] = memory[-20:]

# ------------------- Database Helpers -------------------
def create_conversation(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (session_id, title) VALUES (%s, %s)",
        (session_id, "New Conversation")
    )
    conv_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    conversation_memory[conv_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return conv_id

def get_conversations_by_session(session_uid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, session_id, title, last_updated FROM conversations WHERE session_id = %s ORDER BY last_updated DESC",
        (session_uid,)
    )
    convs = cursor.fetchall()
    cursor.close()
    conn.close()
    return convs

def save_message(conversation_id, role, content, sentiment_score=None, sentiment_label=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, sentiment_score, sentiment_label) VALUES (%s, %s, %s, %s, %s)",
        (conversation_id, role, content, sentiment_score, sentiment_label)
    )
    conn.commit()
    cursor.close()
    conn.close()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET last_updated = NOW() WHERE id = %s", (conversation_id,))
    conn.commit()
    cursor.close()
    conn.close()

def update_conversation_title(conversation_id, title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = %s WHERE id = %s", (title, conversation_id))
    conn.commit()
    cursor.close()
    conn.close()

def auto_generate_title(user_message):
    cleaned = re.sub(r'[^\w\s]', '', user_message.lower())
    words = cleaned.split()
    topic_keywords = {
        "login": ["login", "sign", "authentication"],
        "design": ["design", "look", "ui", "interface"],
        "speed": ["speed", "fast", "slow", "loading"],
        "booking": ["book", "reserve", "room", "hostel"],
        "complaint": ["bad", "terrible", "awful", "dirty", "broken"],
        "praise": ["good", "great", "excellent", "love", "amazing"],
        "feature": ["feature", "function", "option", "tool"]
    }
    topics = []
    for topic, keywords in topic_keywords.items():
        if any(kw in cleaned for kw in keywords):
            topics.append(topic.capitalize())
    if topics:
        title = " ".join(topics[:2])
        if len(title.split()) > 5:
            title = " ".join(title.split()[:5])
        return title
    if len(words) >= 3:
        return " ".join(words[:3]).capitalize()
    else:
        return user_message[:30].capitalize()

def get_messages_for_conversation(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT role, content, timestamp FROM messages WHERE conversation_id = %s ORDER BY timestamp ASC",
        (conversation_id,)
    )
    msgs = cursor.fetchall()
    cursor.close()
    conn.close()
    return msgs

# ------------------- Flask Routes -------------------
@app.route("/")
def home():
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())
    return render_template("index.html")

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    user_sid = session.get('user_session_id')
    if not user_sid:
        return jsonify([])
    convs = get_conversations_by_session(user_sid)
    return jsonify(convs)

@app.route("/api/conversations", methods=["POST"])
def new_conversation():
    user_sid = session.get('user_session_id')
    if not user_sid:
        user_sid = str(uuid.uuid4())
        session['user_session_id'] = user_sid
    conv_id = create_conversation(user_sid)
    return jsonify({"conversation_id": conv_id, "title": "New Conversation"})

@app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
def get_messages(conv_id):
    msgs = get_messages_for_conversation(conv_id)
    return jsonify(msgs)

@app.route("/api/chat_stream", methods=["POST"])
def chat_stream():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return jsonify({"error": "No conversation_id"}), 400

    # 1. Save user message and analyse sentiment
    polarity, label = analyze_sentiment(user_message)
    save_message(conversation_id, "user", user_message, polarity, label)
    update_memory(conversation_id, "user", user_message)

    # Get session_id for aspect logging
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_id FROM conversations WHERE id = %s", (conversation_id,))
    row = cursor.fetchone()
    session_id = row[0] if row else str(conversation_id)
    cursor.close()
    conn.close()
    log_aspects(session_id, user_message, label, polarity)

    # Auto-title on first message
    msg_count = len(get_messages_for_conversation(conversation_id))
    if msg_count == 1:
        title = auto_generate_title(user_message)
        update_conversation_title(conversation_id, title)

    # Inject explicit feedback into memory
    inject_explicit_feedback_into_memory(conversation_id)

    # Check rule-based follow-up (fast path)
    followup_q, trigger = should_ask_followup(user_message, label)
    if followup_q:
        bot_reply = followup_q
        log_followup(session_id, user_message, followup_q, bot_reply)
        # For follow-up, we can still stream it character by character
        def generate_followup():
            avg_rating = compute_conversation_rating(conversation_id)
            yield f"data: {json.dumps({'rating': avg_rating})}\n\n"
            for i, char in enumerate(bot_reply):
                yield f"data: {json.dumps({'chunk': char, 'done': False})}\n\n"
                time.sleep(0.02)
            yield f"data: {json.dumps({'done': True})}\n\n"
            save_message(conversation_id, "assistant", bot_reply)
            update_memory(conversation_id, "assistant", bot_reply)
        return Response(stream_with_context(generate_followup()), mimetype="text/event-stream")

    # 2. Generate full bot reply using the LLM
    memory = get_memory(conversation_id)
    if not memory or memory[0].get("role") != "system":
        memory.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    memory_for_gen = memory + [{"role": "user", "content": user_message}]
    prompt = tokenizer.apply_chat_template(memory_for_gen, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    input_length = inputs.input_ids.shape[1]
    bot_reply = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()
    # Enforce Mr Hero identity
    bot_reply = re.sub(r'(?i)(Alibaba|Aliyun|Alibaba Cloud)', 'Iheruo Ugochukwu R', bot_reply)
    if 'Iheruo' not in bot_reply and 'Mr Iheruo' not in bot_reply:
        bot_reply =bot_reply

    # 3. Stream the reply character by character
    def generate():
        avg_rating = compute_conversation_rating(conversation_id)
        yield f"data: {json.dumps({'rating': avg_rating})}\n\n"
        for char in bot_reply:
            yield f"data: {json.dumps({'chunk': char, 'done': False})}\n\n"
            time.sleep(0.02)   # simulate typing
        yield f"data: {json.dumps({'done': True})}\n\n"
        # Save after streaming
        save_message(conversation_id, "assistant", bot_reply)
        update_memory(conversation_id, "assistant", bot_reply)
        # Periodically save insights
        user_msg_count = len([m for m in get_messages_for_conversation(conversation_id) if m['role'] == 'user'])
        if user_msg_count % 5 == 0:
            save_session_insights(session_id)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/api/conversation_analytics/<int:conversation_id>")
def conversation_analytics(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Sentiment timeline
    cursor.execute("""
        SELECT sentiment_score, sentiment_label, timestamp 
        FROM messages 
        WHERE conversation_id = %s AND role='user' AND sentiment_score IS NOT NULL
        ORDER BY timestamp ASC
    """, (conversation_id,))
    timeline = cursor.fetchall()
    # Aspect summary
    cursor.execute("""
        SELECT aspect, sentiment_label, COUNT(*) as count
        FROM aspect_sentiments
        WHERE session_id = (SELECT session_id FROM conversations WHERE id = %s)
        GROUP BY aspect, sentiment_label
    """, (conversation_id,))
    aspects = cursor.fetchall()
    # Explicit feedback
    cursor.execute("SELECT rating, comment, timestamp FROM explicit_feedback WHERE conversation_id = %s", (conversation_id,))
    explicit = cursor.fetchall()
    # Insights
    cursor.execute("SELECT insights_json FROM feedback_summary WHERE session_id = (SELECT session_id FROM conversations WHERE id = %s)", (conversation_id,))
    row = cursor.fetchone()
    insights = json.loads(row['insights_json']) if row and row['insights_json'] else {}
    cursor.close()
    conn.close()
    return jsonify({
        "timeline": timeline,
        "aspects": aspects,
        "explicit_feedback": explicit,
        "insights": insights
    })

@app.route("/api/explicit_feedback", methods=["POST"])
def add_explicit_feedback():
    data = request.get_json()
    conversation_id = data.get("conversation_id")
    rating = data.get("rating")
    comment = data.get("comment", "")
    if not conversation_id or not rating:
        return jsonify({"error": "Missing data"}), 400
    
    # 1. Save explicit feedback to its own table
    save_explicit_feedback(conversation_id, rating, comment)
    
    # 2. Create a user message representing the explicit feedback
    user_feedback_msg = f"📝 Explicit feedback: {rating}/5 stars. {comment if comment else 'No comment provided.'}"
    polarity, label = analyze_sentiment(user_feedback_msg)
    save_message(conversation_id, "user", user_feedback_msg, polarity, label)
    update_memory(conversation_id, "user", user_feedback_msg)
    
    # 3. Inject into memory
    inject_explicit_feedback_into_memory(conversation_id)
    
    # 4. Generate bot acknowledgment
    memory = get_memory(conversation_id)
    temp_user_msg = {
        "role": "user",
        "content": f"I just gave explicit feedback: rating {rating}/5, comment: '{comment}'. Please acknowledge it."
    }
    memory_for_gen = memory + [temp_user_msg]
    prompt = tokenizer.apply_chat_template(memory_for_gen, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    input_length = inputs.input_ids.shape[1]
    ack_reply = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()
    ack_reply = re.sub(r'(?i)(Alibaba|Aliyun|Alibaba Cloud)', 'Iheruo Ugochukwu R', ack_reply)
    
    # Save bot acknowledgment
    save_message(conversation_id, "assistant", ack_reply)
    update_memory(conversation_id, "assistant", ack_reply)
    
    return jsonify({"status": "ok", "acknowledgment": ack_reply})

@app.route("/api/reset", methods=["POST"])
def reset():
    return jsonify({"status": "ok"})

@app.route("/analytics")
def global_analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT sentiment_label, COUNT(*) as cnt FROM messages WHERE role='user' GROUP BY sentiment_label")
    sentiment_counts = {row['sentiment_label']: row['cnt'] for row in cursor.fetchall()}
    cursor.execute("SELECT aspect, sentiment_label, COUNT(*) as cnt FROM aspect_sentiments GROUP BY aspect, sentiment_label")
    aspect_data = cursor.fetchall()
    cursor.execute("SELECT COUNT(DISTINCT session_id) as total FROM conversations")
    total_sessions = cursor.fetchone()['total']
    cursor.close()
    conn.close()
    return jsonify({
        "total_sessions": total_sessions,
        "sentiment_distribution": sentiment_counts,
        "aspect_sentiment": aspect_data
    })

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=7860, threaded=True)
