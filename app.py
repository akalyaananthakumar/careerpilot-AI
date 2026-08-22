import os
import time

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

from chatbot_config import CHATBOT_CONFIG

load_dotenv()

app = Flask(__name__)

# ==============================
# GEMINI CONFIGURATION
# ==============================

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

client = None

if API_KEY:
    client = genai.Client(api_key=API_KEY)


# ==============================
# DOMAIN CHECK
# ==============================

def is_domain_question(message):
    """
    Check whether the user's message contains
    at least one domain-related keyword.
    """

    message = message.lower().strip()

    keywords = CHATBOT_CONFIG.get(
        "domain_keywords",
        []
    )

    for keyword in keywords:

        if keyword.lower() in message:
            return True

    return False


# ==============================
# CLEAN CHAT HISTORY
# ==============================

def clean_history(history):

    if not isinstance(history, list):
        return []

    cleaned = []

    for item in history[-10:]:

        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content", "")

        if role not in ["user", "model"]:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if not content:
            continue

        cleaned.append(
            types.Content(
                role=role,
                parts=[
                    types.Part.from_text(
                        text=content[:5000]
                    )
                ]
            )
        )

    return cleaned


# ==============================
# HOME PAGE
# ==============================

@app.route("/")
def home():

    return render_template(
        "index.html",
        config=CHATBOT_CONFIG
    )


# ==============================
# HEALTH CHECK
# ==============================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "api_configured": bool(API_KEY),
        "model": MODEL,
        "domain": CHATBOT_CONFIG.get(
            "title",
            "AI Chatbot"
        ),
        "authentication": False,
        "database": False
    })


# ==============================
# CHAT API
# ==============================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        # --------------------------------
        # CHECK REQUEST
        # --------------------------------

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify({
                "error": "Invalid JSON request."
            }), 400

        message = data.get(
            "message",
            ""
        )

        history = data.get(
            "history",
            []
        )

        if not isinstance(message, str):

            return jsonify({
                "error": "Message must be text."
            }), 400

        message = message.strip()

        if not message:

            return jsonify({
                "error": "Please enter a message."
            }), 400

        if len(message) > 6000:

            return jsonify({
                "error":
                    "Message is too long. "
                    "Please keep it under 6000 characters."
            }), 400


        # --------------------------------
        # STRICT DOMAIN PROTECTION
        # --------------------------------

        if not is_domain_question(message):

            return jsonify({
                "reply":
                    CHATBOT_CONFIG[
                        "out_of_domain"
                    ]
            })


        # --------------------------------
        # CHECK API KEY
        # --------------------------------

        if not API_KEY:

            return jsonify({
                "error":
                    "Gemini API key is missing. "
                    "Add GEMINI_API_KEY to your .env file."
            }), 500


        # --------------------------------
        # CLEAN HISTORY
        # --------------------------------

        cleaned_history = clean_history(
            history
        )


        # --------------------------------
        # CURRENT USER MESSAGE
        # --------------------------------

        current_message = types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=message
                )
            ]
        )

        contents = (
            cleaned_history
            + [current_message]
        )


        # --------------------------------
        # GEMINI REQUEST WITH RETRIES
        # --------------------------------

        response = None
        last_error = None

        for attempt in range(3):

            try:

                print(
                    f"Gemini request "
                    f"attempt {attempt + 1}/3"
                )

                response = client.models.generate_content(

                    model=MODEL,

                    contents=contents,

                    config=types.GenerateContentConfig(

                        system_instruction=
                            CHATBOT_CONFIG[
                                "system_prompt"
                            ],

                        temperature=0.7,

                        max_output_tokens=1200,

                        automatic_function_calling=
                            types.AutomaticFunctionCallingConfig(
                                disable=True
                            )
                    )
                )

                break


            except Exception as error:

                last_error = error

                error_text = str(
                    error
                ).upper()

                print(
                    "Gemini error:"
                )

                print(
                    repr(error)
                )


                # Temporary errors
                temporary_error = (
                    "503" in error_text
                    or
                    "UNAVAILABLE" in error_text
                    or
                    "429" in error_text
                    or
                    "500" in error_text
                )


                if temporary_error:

                    if attempt < 2:

                        wait_time = (
                            2 ** attempt
                        )

                        print(
                            f"Retrying in "
                            f"{wait_time} seconds..."
                        )

                        time.sleep(
                            wait_time
                        )

                        continue


                # Non-temporary error
                break


        # --------------------------------
        # NO RESPONSE
        # --------------------------------

        if response is None:

            error_text = str(
                last_error or ""
            )

            error_upper = error_text.upper()


            if (
                "503" in error_upper
                or
                "UNAVAILABLE" in error_upper
            ):

                return jsonify({
                    "error":
                        "Gemini is temporarily busy. "
                        "Please wait a few seconds and try again."
                }), 503


            if "429" in error_upper:

                return jsonify({
                    "error":
                        "Gemini API request limit reached. "
                        "Please wait and try again."
                }), 429


            if (
                "401" in error_upper
                or
                "API KEY" in error_upper
            ):

                return jsonify({
                    "error":
                        "Your Gemini API key is invalid "
                        "or missing."
                }), 401


            if "404" in error_upper:

                return jsonify({
                    "error":
                        f"The model '{MODEL}' "
                        "was not found. Check GEMINI_MODEL."
                }), 404


            print(
                "Final Gemini error:",
                repr(last_error)
            )

            return jsonify({
                "error":
                    "Gemini could not generate a response. "
                    "Check the terminal for details."
            }), 500


        # --------------------------------
        # GET RESPONSE TEXT
        # --------------------------------

        answer = ""

        try:
            answer = (
                response.text or ""
            ).strip()

        except Exception:
            answer = ""


        if not answer:

            return jsonify({
                "error":
                    "Gemini returned an empty response."
            }), 500


        # --------------------------------
        # SUCCESS
        # --------------------------------

        return jsonify({

            "reply": answer,

            "model": MODEL,

            "success": True
        })


    except Exception as error:

        print(
            "\n=============================="
        )

        print(
            "FLASK CHAT ERROR:"
        )

        print(
            repr(error)
        )

        print(
            "==============================\n"
        )

        return jsonify({
            "error":
                "Something went wrong on the server. "
                "Check the terminal."
        }), 500


# ==============================
# ERROR HANDLERS
# ==============================

@app.errorhandler(404)
def not_found(error):

    if request.path == "/chat":

        return jsonify({
            "error":
                "The /chat endpoint was not found."
        }), 404

    return render_template(
        "index.html",
        config=CHATBOT_CONFIG
    ), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "error":
            "This HTTP method is not allowed."
    }), 405


@app.errorhandler(500)
def server_error(error):

    if request.path == "/chat":

        return jsonify({
            "error":
                "Internal server error. "
                "Check the Flask terminal."
        }), 500

    return jsonify({
        "error":
            "Internal server error."
    }), 500


# ==============================
# RUN
# ==============================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )