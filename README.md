# Voice Command Recognition using AWS Lex V2 & Serverless Lambda
**Cloud Computing Academic Project • 100% Free Tier ($0 Cost)**

---

## 📌 Project Overview
This project implements an **End-to-End Voice Command Recognition and Smart Home Automation System** using Amazon Web Services (AWS). It leverages:
- **Amazon Lex V2**: Dual-engine Automatic Speech Recognition (ASR) & Natural Language Understanding (NLU).
- **AWS Lambda**: Serverless FaaS (Function-as-a-Service) for event-driven backend fulfillment.
- **Amazon Polly**: Text-to-Speech (TTS) voice synthesis for conversational voice replies.
- **Web Audio API + Python Flask**: Modern interactive frontend displaying live audio waveform, real-time virtual device states, cloud telemetry, intent confidence, and raw Lex JSON payloads.

---

## 🏗️ Cloud Architecture & Flow
```
User (Voice/Mic) 
       │ (16kHz Mono PCM Audio Stream)
       ▼
Web Frontend (Web Audio API)
       │ HTTP POST /api/command/voice
       ▼
Flask Backend Gateway (Boto3)
       │ RecognizeUtterance API
       ▼
AWS Lex V2 Engine
  ├── 1. Automatic Speech Recognition (ASR) -> Transcribes audio to text
  └── 2. Natural Language Understanding (NLU) -> Classifies Intent & extracts Slots
       │ Fulfillment Event (JSON)
       ▼
AWS Lambda Function (Serverless Python 3.12)
       │ Executes business logic & updates device representation
       ▼
AWS Lex V2 -> Amazon Polly (Synthesizes spoken audio reply)
       │
       ▼
Client Web Dashboard:
  ├── Audio playback of Polly response
  ├── Virtual Devices toggle (Bulb glows, Fan rotates, AC temperature updates)
  └── Telemetry panel displays Intent, Slots, Latency, and JSON Tree
```

---

## 💰 AWS Free Tier & Zero-Cost ($0) Guarantee
All services used in this project fall safely within the AWS Free Tier:
| Service | Free Tier Monthly Allowance | Project Usage |
| :--- | :--- | :--- |
| **Amazon Lex V2** | 10,000 text requests & 1,500 speech requests/mo (12 mo free) | ~50 - 100 requests (Well within limit) |
| **AWS Lambda** | 1,000,000 invocations & 3.2M seconds of compute/mo (Always Free) | ~100 invocations |
| **Amazon CloudWatch** | 5GB log data ingestion, 10 custom metrics/alarms (Always Free) | < 10 MB logs |
| **Amazon Polly** | Synthesized speech output included with Lex speech requests | Included |

---

## 🚀 Quick Start Guide

### 1. Run in Offline / Mock Mode (Zero Setup)
You can test the entire UI, voice recording, animated devices, and simulated responses immediately:
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### 2. Connect to Live AWS Cloud
Once your AWS Lex Bot and Lambda function are created:
1. Open `.env` and set `MOCK_AWS=false`.
2. Add your `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `LEX_BOT_ID`.
3. Restart `python app.py`.

---

## 🎓 Academic Viva Questions & Answers

1. **Q: What is the difference between AWS Lex V1 and V2?**  
   *A:* Lex V2 provides a hierarchical bot model supporting multiple languages under a single bot, streaming audio APIs, simplified slot elicitation, and separate builder vs. runtime endpoints.

2. **Q: How does Lex distinguish between Automatic Speech Recognition (ASR) and Natural Language Understanding (NLU)?**  
   *A:* ASR translates the acoustic voice waveform into text tokens ("Speech-to-Text"). NLU parses that text to classify the user's goal (Intent) and extract specific variable entities (Slots).

3. **Q: What is a Lambda Cold Start and how does it affect voice interaction?**  
   *A:* A cold start occurs when an invocation triggers the initialization of a new container runtime. It adds 200–500ms of latency on the first invocation. Subsequent calls execute in a warm container (<30ms).

4. **Q: How is security ensured in this cloud architecture?**  
   *A:* The architecture applies the Principle of Least Privilege: the client IAM user only possesses `lex:RecognizeUtterance` and `lex:RecognizeText` permissions, and Lambda only has basic CloudWatch logging permissions.
