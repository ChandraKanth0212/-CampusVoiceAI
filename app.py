
import os
import json
import re
import subprocess
import uuid
import wave
from difflib import SequenceMatcher
from functools import lru_cache
from unicodedata import normalize as unicode_normalize

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

import imageio_ffmpeg
from services.gnani_stt import transcribe_audio
from services.gnani_tts import generate_speech

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "static/audio"
FAQ_FILE = "data/faq.json"
KNOWLEDGE_BASE_FILE = "data/knowledge_base.json"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)


SUPPORTED_LANGUAGES = {"te-IN", "en-IN", "hi-IN"}
SUPPORTED_INPUT_MODES = {"auto", "te-IN", "en-IN", "hi-IN", "tenglish"}
SUPPORTED_OUTPUT_MODES = {"same", "te-IN", "en-IN", "hi-IN", "tenglish"}
GNANI_MODEL = "prisma-v3.0"


def detect_language(question):
    if re.search(r"[\u0c00-\u0c7f]", question):
        return "te-IN"
    if re.search(r"[\u0900-\u097f]", question):
        return "hi-IN"
    return "en-IN"


def normalize_language(input_language, question):
    if input_language in {"te-IN", "en-IN", "hi-IN"}:
        return input_language
    if input_language == "tenglish":
        return "en-IN"
    return detect_language(question)


def stt_configuration(input_language):
    if input_language == "auto":
        return "indic-auto", "transcribe"
    if input_language == "tenglish":
        return "te-IN,en-IN", "codemix"
    return input_language, "transcribe"


def _normalize_query(question):
    query = unicode_normalize("NFKC", question).lower()
    query = re.sub(r"[^\w\s\u0c00-\u0c7f\u0900-\u097f+#]", " ", query)
    return re.sub(r"\s+", " ", query).strip()


def _query_tokens(question):
    return set(re.findall(r"[a-z0-9+#\u0900-\u097f\u0c00-\u0c7f]+", _normalize_query(question)))


@lru_cache(maxsize=1)
def _load_knowledge_base():
    with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def _load_faqs():
    with open(FAQ_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _intent_score(query, tokens, terms):
    score = 0.0
    for term in terms:
        normalized_term = _normalize_query(term)
        if " " in normalized_term:
            if normalized_term in query:
                score = max(score, 3.0 + len(normalized_term.split()) * 0.25)
            continue
        if normalized_term in tokens:
            score = max(score, 2.0)
            continue
        if len(normalized_term) >= 5:
            similarity = max(
                SequenceMatcher(None, normalized_term, token).ratio()
                for token in tokens
            ) if tokens else 0
            if similarity >= 0.82:
                score = max(score, 1.25)
    return score


def classify_question(question):
    """Return the best knowledge intent, or None for unrelated questions."""
    query = _normalize_query(question)
    tokens = _query_tokens(question)
    best_intent = None
    best_score = 0.0
    for intent in _load_knowledge_base():
        score = _intent_score(query, tokens, intent["terms"])
        if score > best_score:
            best_intent = intent
            best_score = score
    if best_score >= 1.25:
        return best_intent["id"]
    return None


def _localized_fallback(output_language, kind="unknown"):
    messages = {
        "unknown": {
            "en-IN": "I'm CampusVoice AI, your college assistant. I can help with academics, examinations, programming, placements, careers, and campus life. Please ask a college-related question.",
            "te-IN": "నేను CampusVoice AI, మీ కళాశాల సహాయకుడిని. అకడమిక్స్, పరీక్షలు, ప్రోగ్రామింగ్, ప్లేస్‌మెంట్స్, కెరీర్ మరియు క్యాంపస్ జీవితం గురించి సహాయం చేయగలను. కళాశాలకు సంబంధించిన ప్రశ్న అడగండి.",
            "hi-IN": "मैं CampusVoice AI, आपका कॉलेज सहायक हूं। मैं पढ़ाई, परीक्षाओं, प्रोग्रामिंग, प्लेसमेंट, करियर और कैंपस जीवन में मदद कर सकता हूं। कॉलेज से जुड़ा प्रश्न पूछें।",
            "tenglish": "Nenu CampusVoice AI, mee college assistant ni. Academics, exams, programming, placements, careers and campus life gurinchi help cheyyagalanu. College-related question adugandi."
        },
        "official": {
            "en-IN": "I don't have a verified institutional document for that detail. Please check the latest official college notice, portal, handbook, or the responsible office.",
            "te-IN": "ఆ వివరాలకు ధృవీకరించిన కళాశాల డాక్యుమెంట్ నా వద్ద లేదు. తాజా అధికారిక నోటీసు, పోర్టల్, హ్యాండ్‌బుక్ లేదా సంబంధిత కార్యాలయాన్ని సంప్రదించండి.",
            "hi-IN": "इस विवरण के लिए मेरे पास सत्यापित कॉलेज दस्तावेज नहीं है। नवीनतम आधिकारिक सूचना, पोर्टल, हैंडबुक या संबंधित कार्यालय से पुष्टि करें।",
            "tenglish": "Aa detail ki verified college document naa daggara ledu. Latest official notice, portal, handbook or responsible office tho confirm cheyyandi."
        }
    }
    return messages[kind][output_language]


def get_answer(question, output_language="en-IN"):
    intent_id = classify_question(question)
    if intent_id:
        intent = next(item for item in _load_knowledge_base() if item["id"] == intent_id)
        return intent["responses"].get(output_language, intent["responses"]["en-IN"])

    question_words = _query_tokens(question)
    best_answer = None
    best_score = 0.0

    for faq in _load_faqs():
        score = sum(1 for keyword in faq["keywords"] if _normalize_query(keyword) in question_words)
        if score > best_score:
            best_score = score
            best_answer = faq.get("responses", {}).get(
                output_language,
                faq["answer"]
            )

    if best_answer and best_score >= 2:
        return best_answer
    return _localized_fallback(output_language)


def create_answer_response(question, input_language, output_language):
    detected_language = normalize_language(input_language, question)
    if output_language == "same":
        output_language = "tenglish" if input_language == "tenglish" else detected_language
    tts_language = output_language if output_language in SUPPORTED_LANGUAGES else "en-IN"
    answer = get_answer(question, output_language)
    audio_name = f"{uuid.uuid4().hex}.wav"
    output_path = os.path.join(AUDIO_FOLDER, audio_name)
    generate_speech(answer, output_path=output_path, language=tts_language)
    return {
        "success": True,
        "question": question,
        "answer": answer,
        "audio_url": f"/static/audio/{audio_name}",
        "detected_language": detected_language,
        "output_language": output_language,
        "tts_language": tts_language,
    }


def convert_to_wav(input_path, output_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y", "-i", input_path,
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", output_path
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    try:
        with wave.open(output_path, "rb") as wav_file:
            if (
                wav_file.getnchannels() != 1
                or wav_file.getsampwidth() != 2
                or wav_file.getframerate() != 16000
            ):
                raise ValueError("Converted audio is not mono 16-bit 16 kHz PCM")
            if wav_file.getnframes() == 0:
                raise ValueError("Converted audio is empty")
    except (wave.Error, OSError) as error:
        raise ValueError("Converted audio is not a valid WAV file") from error


@app.route("/")
def home():
    return send_from_directory("templates", "index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    audio_path = None
    wav_path = None
    try:
        if "audio" not in request.files:
            return jsonify({
                "success": False,
                "error": "No audio file received"
            }), 400

        audio_file = request.files["audio"]

        if not audio_file.filename:
            return jsonify({
                "success": False,
                "error": "Empty audio filename"
            }), 400

        filename = secure_filename(audio_file.filename) or "recording"
        input_language = request.form.get("input_language", request.form.get("language", "te-IN"))
        output_language = request.form.get("output_language", "same")
        if input_language not in SUPPORTED_INPUT_MODES:
            return jsonify({"success": False, "error": "Unsupported language"}), 400
        if output_language not in SUPPORTED_OUTPUT_MODES:
            return jsonify({"success": False, "error": "Unsupported response language"}), 400
        recognition_language, recognition_format = stt_configuration(input_language)

        audio_path = os.path.join(
            UPLOAD_FOLDER,
            f"{uuid.uuid4().hex}_{filename}"
        )
        audio_file.save(audio_path)
        wav_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.wav")
        convert_to_wav(audio_path, wav_path)
        transcription = transcribe_audio(
            wav_path,
            language=recognition_language,
            model=GNANI_MODEL,
            output_format=recognition_format,
            return_metadata=True,
        )
        transcript = transcription["transcript"]

        if not transcript.strip():
            return jsonify({
                "success": False,
                "error": "Could not recognize speech"
            }), 422

        if request.form.get("transcribe_only", "").lower() == "true":
            return jsonify({
                "success": True,
                "transcript": transcript,
                "stt": {
                    "model": transcription["model"],
                    "requested_language": transcription["requested_language"],
                    "detected_language": transcription["detected_language"],
                    "format": transcription["format"],
                },
            })

        response = create_answer_response(transcript, input_language, output_language)
        response["transcript"] = transcript
        response["stt"] = {
            "model": transcription["model"],
            "requested_language": transcription["requested_language"],
            "detected_language": transcription["detected_language"],
            "format": transcription["format"],
        }
        return jsonify(response)

    except Exception as error:
        app.logger.exception("Voice request failed")

        return jsonify({
            "success": False,
            "error": "We could not process that recording. Please try again."
        }), 500
    finally:
        for path in (audio_path, wav_path):
            if path and os.path.exists(path):
                os.remove(path)


@app.route("/api/text", methods=["POST"])
def text():
    try:
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        input_language = payload.get("input_language", payload.get("language", "auto"))
        output_language = payload.get("output_language", "same")
        if not question:
            return jsonify({"success": False, "error": "Please enter a question."}), 400
        if input_language not in SUPPORTED_INPUT_MODES:
            return jsonify({"success": False, "error": "Unsupported language"}), 400
        if output_language not in SUPPORTED_OUTPUT_MODES:
            return jsonify({"success": False, "error": "Unsupported response language"}), 400
        return jsonify(create_answer_response(question, input_language, output_language))
    except Exception:
        app.logger.exception("Text request failed")
        return jsonify({
            "success": False,
            "error": "We could not prepare an answer. Please try again."
        }), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
