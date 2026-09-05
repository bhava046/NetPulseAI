from flask import Flask, jsonify, render_template, request, redirect, session
import json
import os
from google import genai

app = Flask(__name__)
app.secret_key = "netpulse-secret-key"


# ==================================================
# LOAD ALERTS
# ==================================================

def load_alerts():
    with open("data/alerts.json", "r") as file:
        return json.load(file)


# ==================================================
# LOAD RUNBOOKS
# ==================================================

def load_runbooks():
    with open("data/runbooks.json", "r") as file:
        return json.load(file)


# ==================================================
# LOCAL FALLBACK ANALYSIS
# ==================================================

def fallback_analysis():

    return {
        "status": "fallback",

        "incidents": [

            {
                "incident_id": "INC001",
                "title": "Possible WAN Connectivity Incident",
                "priority": "HIGH",

                "alerts": [
                    "A001",
                    "A002",
                    "A003",
                    "A005"
                ],

                "reason":
                    "The WAN link failure on Router-R1 "
                    "is followed by multiple connectivity problems.",

                "runbook": "RB001",

                "recommendation":
                    "Check Router-R1 WAN interface, "
                    "physical connection and backup link.",

                "root_cause":
                    "Router-R1 primary WAN link failure "
                    "is the most likely root cause.",

                "confidence": 92,

                "impact":
                    "Switch-S1 and Servers S1/S2 may be affected.",

                "action":
                    "Check WAN interface status and "
                    "physical connectivity first."
            },

            {
                "incident_id": "INC002",
                "title": "Authentication Failure",
                "priority": "MEDIUM",

                "alerts": [
                    "A004"
                ],

                "reason":
                    "Repeated authentication failures "
                    "were detected on Router-R1.",

                "runbook": "RB002",

                "recommendation":
                    "Check authentication logs "
                    "and verify device credentials.",

                "root_cause":
                    "Possible unauthorized access attempt "
                    "or incorrect credentials.",

                "confidence": 78,

                "impact":
                    "Router-R1 security may be affected.",

                "action":
                    "Review authentication logs and "
                    "verify recent login attempts."
            }
        ]
    }


# ==================================================
# AI INCIDENT ANALYSIS
# ==================================================

def analyze_with_ai(alerts, runbooks):

    api_key = os.getenv("GEMINI_API_KEY")

    # If API key is not available,
    # use local analysis
    if not api_key:
        return fallback_analysis()

    try:

        client = genai.Client(
            api_key=api_key
        )

        prompt = f"""
You are NetPulse AI.

You are a Network Incident Triage Assistant.

Analyze the following network alerts and runbooks.

ALERTS:
{json.dumps(alerts, indent=2)}

RUNBOOKS:
{json.dumps(runbooks, indent=2)}

Tasks:

1. Group related alerts into incidents.
2. Identify priority as HIGH, MEDIUM or LOW.
3. Explain why alerts are grouped.
4. Match each incident with a suitable runbook.
5. Give a recommended troubleshooting action.
6. Predict the most likely root cause.
7. Give confidence from 0 to 100.
8. Explain possible impact.
9. Give the first recommended action.

Do not claim that the root cause is 100% certain.

Return ONLY valid JSON.

Use this format:

{{
    "incidents": [
        {{
            "incident_id": "INC001",
            "title": "Incident title",
            "priority": "HIGH",
            "alerts": ["A001", "A002"],
            "reason": "Reason for grouping",
            "runbook": "RB001",
            "recommendation": "Recommended action",
            "root_cause": "Most likely root cause",
            "confidence": 92,
            "impact": "Possible network impact",
            "action": "First recommended action"
        }}
    ]
}}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # Remove markdown code block if Gemini returns it
        if text.startswith("```"):

            text = text.replace("```json", "")
            text = text.replace("```", "")
            text = text.strip()

        result = json.loads(text)

        # Make sure required fields exist
        for incident in result.get("incidents", []):

            if "root_cause" not in incident:
                incident["root_cause"] = (
                    "Root cause could not be determined with certainty."
                )

            if "confidence" not in incident:
                incident["confidence"] = 70

            if "impact" not in incident:
                incident["impact"] = (
                    "Potential impact on connected network devices."
                )

            if "action" not in incident:
                incident["action"] = (
                    incident.get(
                        "recommendation",
                        "Check the affected device."
                    )
                )

        return {
            "status": "ai",
            **result
        }

    except Exception as e:

        print("AI ANALYSIS ERROR:", e)

        # If Gemini fails,
        # still show local result
        return fallback_analysis()


# ==================================================
# LOGIN
# ==================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "1234":

            session["logged_in"] = True
            session["username"] = username

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/")

    return render_template("index.html")


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==================================================
# ALERTS
# ==================================================

@app.route("/alerts")
def alerts():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Please login first."
        }), 401

    return jsonify(load_alerts())


# ==================================================
# RUNBOOKS
# ==================================================

@app.route("/runbooks")
def runbooks():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Please login first."
        }), 401

    return jsonify(load_runbooks())


# ==================================================
# AI ANALYZE
# ==================================================

@app.route("/analyze")
def analyze():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Please login first."
        }), 401

    alerts_data = load_alerts()
    runbooks_data = load_runbooks()

    result = analyze_with_ai(
        alerts_data,
        runbooks_data
    )

    return jsonify(result)


# ==================================================
# ASK NETPULSE AI
# ==================================================

@app.route("/ask", methods=["POST"])
def ask():

    try:

        # Check login
        if not session.get("logged_in"):

            return jsonify({
                "answer": "Please login first."
            }), 401

        # Get JSON data
        data = request.get_json()

        if not data:

            return jsonify({
                "answer": "No question received."
            })

        question = data.get(
            "question",
            ""
        ).strip()

        if not question:

            return jsonify({
                "answer": "Please type your question."
            })

        # Get Gemini API key
        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        # If API key missing
        if not api_key:

            return jsonify({
                "answer":
                    "Gemini API key is not configured."
            })

        # Gemini client
        client = genai.Client(
            api_key=api_key
        )

        # Load current network data
        alerts_data = load_alerts()
        runbooks_data = load_runbooks()

        # AI prompt
        prompt = f"""
You are NetPulse AI.

You are a Network Incident Triage Assistant.

CURRENT NETWORK ALERTS:

{json.dumps(alerts_data, indent=2)}

AVAILABLE RUNBOOKS:

{json.dumps(runbooks_data, indent=2)}

USER QUESTION:

{question}

Answer in simple and clear language.

Use the current network alerts and runbooks
when relevant.

Do not claim that a root cause is completely certain.

If the issue is serious, recommend contacting
a network engineer.

Keep the answer short and useful.
"""

        # IMPORTANT:
        # Gemini 2.5 Flash
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return jsonify({
            "answer": response.text
        })

    except Exception as e:

        print(
            "ASK ERROR:",
            e
        )

        return jsonify({
            "answer":
                "AI service error. Please check the Flask terminal."
        }), 500


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )