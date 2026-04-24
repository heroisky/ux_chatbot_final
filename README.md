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
- Dashboard: PHP (XAMPP / WAMP)
- Libraries: PyTorch, gdown

---

## 📁 Project Structure

```
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
│   └── ...
│
├── sentiment_model/
│   ├── config.json
│   ├── vocab.txt
│   ├── tokenizer_config.json
│   ├── model.safetensors
│   └── ...
│
├── templates/
│   └── index.html
│
└── ux_dashboard/
    └── (PHP analytics dashboard files)
```

---

## ⚠️ Important Note

Models are stored locally:

- `qwen2.5/`
- `sentiment_model/`

They are NOT pushed to GitHub because of size limits.

⚠️ Do NOT use `model_path = "Qwen/Qwen2.5..."` in production unless you want a **multi-GB download (15GB+)**

Instead:
- Use local folders OR
- Auto-download ZIP on first run (Google Drive / HuggingFace snapshot)

---

## ⚙️ Installation

### 1. Clone Project

```bash
git clone https://github.com/heroisky/ux_chatbot_final.git
cd ux_chatbot_final
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv

# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Setup MySQL Database

Start MySQL (XAMPP / WAMP)

Create database:

```sql
CREATE DATABASE ux_feedback_db;
```

Import schema:

```bash
mysql -u root -p ux_feedback_db < database_schema.sql
```

OR use phpMyAdmin:
- http://localhost/phpmyadmin

---

### 5. Add Model Files

Place downloaded models here:

```
qwen2.5/
sentiment_model/
```

---

### 6. Run Flask App

```bash
python app.py
```

Open:

```
http://localhost:7860
```

---

## 📊 Run PHP Dashboard (XAMPP / WAMP)

### 🔹 XAMPP Setup

1. Move project to:

```
C:\xampp\htdocs\ux_chatbot_final\
```

2. Start:
- Apache
- MySQL

3. Open:

```
http://localhost/ux_chatbot_final/ux_dashboard/
```

---

### 🔹 WAMP Setup

1. Move project to:

```
C:\wamp64\www\ux_chatbot_final\
```

2. Start WAMP services

3. Open:

```
http://localhost/ux_chatbot_final/ux_dashboard/
```

---

## 🔄 System Flow

User Input  
→ Sentiment Analysis  
→ Aspect Extraction  
→ Qwen2.5 Response Generation  
→ Follow-up Logic  
→ Store in MySQL  
→ Analytics Dashboard

---

## 📊 Analytics

Flask API:
```
http://localhost:7860/analytics
```

PHP Dashboard:
```
http://localhost/ux_chatbot_final/ux_dashboard/
```

---

## ⚡ Model Warning

- First run may be slow
- Large models require RAM (8GB+ recommended)
- CPU mode is used by default

---

## 🧯 Troubleshooting

### ❌ Model downloads 1GB
✔ You used HuggingFace remote model  
→ Fix: use local `qwen2.5/` folder

---

### ❌ MySQL error
✔ Ensure:
- MySQL running in XAMPP/WAMP
- Correct credentials in `app.py`

---

### ❌ PHP dashboard not opening
✔ Ensure:
- Apache is running
- Folder is inside `htdocs` or `www`

---

### ❌ Blank chatbot response
✔ Check:
- model files exist
- no missing tokenizer files

---

## 👨‍💻 Developer

Iheruo Ugochukwu R.

Final Year Project – UX Feedback System
