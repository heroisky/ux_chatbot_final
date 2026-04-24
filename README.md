# 🤖 UX Feedback Chatbot – Iheruo

A full-stack AI-powered chatbot that collects user experience feedback, performs sentiment analysis, extracts aspects, and generates actionable insights using a conversational LLM and analytics pipeline.

---

## 🚀 Features

- Conversational AI (Qwen2.5 local model)
- Sentiment analysis (positive / negative / neutral)
- Aspect-based feedback extraction (UI, speed, login, etc.)
- Smart follow-up questions for unclear or negative feedback
- Real-time analytics dashboard
- Session-based conversation memory
- Explicit user rating system (1–5 stars)
- Streaming chatbot responses (typing effect)
- Automatic session insights generation

---

## 🧱 Tech Stack

- Backend: Flask (Python)
- AI Model: Hugging Face Transformers (Qwen2.5)
- Sentiment Model: Local transformer pipeline
- Database: MySQL
- Frontend: HTML, CSS, JavaScript
- Libraries: PyTorch, gdown

---

## 📁 Project Structure

## 📁 Project Structure

ux_chatbot_final/
│
├── app.py
├── app1.py
├── requirements.txt
├── database_schema.sql
│
├── qwen2.5/
│   ├── config.json
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   ├── model.safetensors
│   └── (other model files)
│
├── sentiment_model/
│   ├── config.json
│   ├── vocab.txt
│   ├── tokenizer_config.json
│   ├── model.safetensors
│   └── (other model files)
│
├── templates/
│   └── index.html
│
└── ux_dashboard/
    └── (analytics dashboard files)

---

## ⚠️ Important Note

Models are stored locally:

- qwen2.5/
- sentiment_model/

They are NOT included in GitHub due to large file size limits.

---

## ⚙️ Installation

git clone https://github.com/your-username/ux_chatbot_final.git
cd ux_chatbot_final

python -m venv venv
source venv/bin/activate   (Linux/Mac)
venv\Scripts\activate      (Windows)

pip install -r requirements.txt

CREATE DATABASE ux_feedback_db;

mysql -u root -p ux_feedback_db < database_schema.sql

Place model folders:
qwen2.5/
sentiment_model/

python app.py

---

## 📊 Analytics

http://localhost:7860/analytics

---

## ⚡ Flow

User message → Sentiment analysis → Aspect extraction → Qwen2.5 response → Follow-up logic → Store in MySQL → Insights

---

## 🚫 GitHub Limitation

Not included:
- model.safetensors
- large transformer weights

Use local ZIP or Google Drive download.

---

## 👨‍💻 Developer

Iheruo Ugochukwu R.

Final Year Project – UX Feedback System
