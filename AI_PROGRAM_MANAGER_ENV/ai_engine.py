import json
import re
from datetime import datetime
import os
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

from utils import llm_validate_documents

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")




class AI_AGENT:
    def __init__(self, transcript_file_path, people_file_path,client, model="llama-3.1-8b-instant"):
        self.transcript_file_path = transcript_file_path
        self.people_file_path = people_file_path
        self.llm_model = model
        self.client = client
        self.transcript_text = ""
        self.people_data = {}
        self.reference_date = datetime.now()

        self.outputs = {
            "meeting_type": None,
            "action_items": [],
            "decisions": [],
            "risks": [],
            "open_questions": [],
            "emails": []
        }

    # ---------- FILE READERS ----------
    def transcript_reader(self):
        """
        Reads a transcript file from the specified file path and stores its content.
        It performs validation to ensure the file exists and is not empty.
        Raises:
            FileNotFoundError: If the transcript file does not exist at the specified path.
            ValueError: If the transcript file is empty or contains only whitespace.
            RuntimeError: If any error occurs during file reading operation, wrapping
                          the original exception with a descriptive message.
        Returns:
            None
        """
        
        try:
            if not os.path.exists(self.transcript_file_path):
                raise FileNotFoundError(f"Transcript file not found: {self.transcript_file_path}")

            with open(self.transcript_file_path, "r", encoding="utf-8") as f:
                self.transcript_text = f.read()

            if not self.transcript_text.strip():
                raise ValueError("Transcript file is empty")

        except Exception as e:
            raise RuntimeError(f"Failed to read transcript file: {e}")

    def peope_details_reader(self):
        """
        Reads and parses the people data from a specified JSON file.
        This method checks if the file exists at the given path. If the file does not exist,
        a FileNotFoundError is raised. It attempts to open the file and load its contents as 
        a JSON object. If the loaded data is not a dictionary or is empty, a ValueError is raised.
        In case of a JSON decoding error, a RuntimeError is raised indicating that the file 
        is not valid JSON. Any other exceptions encountered during the file reading process 
        will also result in a RuntimeError with a relevant message.
        Raises:
            FileNotFoundError: If the people file does not exist.
            ValueError: If the JSON data is not a dictionary or is empty.
            RuntimeError: If the file is not valid JSON or if any other error occurs during file reading.
        """

        try:
            if not os.path.exists(self.people_file_path):
                raise FileNotFoundError(f"People file not found: {self.people_file_path}")

            with open(self.people_file_path, "r", encoding="utf-8") as f:
                self.people_data = json.load(f)

            if not isinstance(self.people_data, dict) or not self.people_data:
                raise ValueError("People file JSON is empty or invalid")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"People file is not valid JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to read people file: {e}")

    # ---------- BASIC METADATA ----------
    def identify_meeting_type_from_filename(self):
        """
        Identifies the meeting type from the filename of the transcript file.
        This method extracts the base name of the transcript file path, splits it 
        by the period (.) character, and assigns the first part (before the extension) 
        to the 'meeting_type' key in the outputs dictionary.
        Raises:
            RuntimeError: If there is an error during the identification process.
        """

        try:
            filename = os.path.basename(self.transcript_file_path)
            self.outputs["meeting_type"] = filename.split('.')[0]
        except Exception as e:
            raise RuntimeError(f"Failed to identify meeting type: {e}")

    # ---------- LLM EXTRACTION ----------
    def extract_insights(self):
        """
        Extracts insights from a meeting transcript, including action items, decisions, risks, open questions, and follow-up emails.
        This method constructs a prompt for a language model to analyze the meeting transcript and extract relevant information based on predefined rules. The extracted insights are structured in JSON format and include:
        - Action Items: Tasks assigned to individuals, including details such as assignee, owner, description, priority, evidence, and deadline.
        - Decisions: Clear decisions made during the meeting, including the decision itself, the owner, and evidence.
        - Risks: Potential risks identified during the meeting, including a summary, evidence, severity, and context.
        - Open Questions: Unresolved questions raised during the meeting, including the question text, evidence, and context.
        - Follow-Up Emails: Draft emails for action owners, including recipient details, subject, and body content.
        Raises:
            ValueError: If the language model returns an empty response or invalid JSON.
            RuntimeError: If insight extraction fails due to any other error.
        Returns:
            None: The extracted insights are stored in the instance's outputs attribute.
        """

        try:
            prompt = f"""
                You are an autonomous meeting intelligence agent.

                Base date (today): {self.reference_date.strftime("%Y-%m-%d")}

                Use plain ASCII apostrophe (') instead of smart quotes (’).

                Your task:
                Extract ACTION ITEMS, DECISIONS, RISKS, and OPEN QUESTIONS from the meeting transcript.

                Return ONLY valid JSON. No markdown. No explanation.

                ================ ROLE DEFINITIONS (VERY IMPORTANT) ================

                OWNER:
                - Person who commits, promises, or takes responsibility in conversation.

                ASSIGNEE:
                - Person who must actually perform the task or provide deliverable.

                ================ OWNER & ASSIGNEE RULES ================

                ACTION ITEMS:

                1) If a speaker commits to act
                (examples: "I will", "I can", "I'll reach out", "I should finish"):

                - owner_name = that speaker (with role)
                - assignee = person who must perform task
                    (may be same as owner OR another person mentioned)

                2) If no speaker commits:

                - owner_name = highest authority from people directory
                - assignee = same as owner_name

                Highest authority order:
                Product Manager > Engineering Manager > Team Lead > others

                owner_name and assignee format MUST be:
                "Full Name (Role from people directory)"

                ================ ACTION ITEM EXTRACTION RULES ================

                1. Extract action items when:
                - someone commits OR
                - task is clearly required for delivery.

                2. Each action item MUST include:
                - assignee
                - owner_name
                - description (short task)
                - priority: High / Medium / Low
                - evidence: exact sentence with timestamp:
                    "[HH:MM] Speaker: sentence"
                - deadline_text: exact phrase used
                    Examples: "Friday", "next Tuesday", "today", "end of week"
                - deadline: always null

                3. Do NOT calculate dates.

                ================ DECISION EXTRACTION RULES ================

                1. Extract decisions ONLY when a clear decision is stated or agreed.

                2. Decision owner MUST be the speaker who stated or confirmed decision.

                3. Each decision MUST include:
                - decision
                - owner_name (with role)
                - evidence (exact quote with timestamp)

                ================ RISK EXTRACTION RULES ================

                1. Extract RISKS when someone mentions:
                - possible delays
                - blockers
                - dependencies
                - failures
                - performance or compliance concerns

                2. Each risk MUST include:
                - risk: short summary
                - evidence: exact quote with timestamp
                - seviarity: High / Medium / Low if implied, else empty string
                - context: detailed explanation of why this is a risk,
                    including relevant people and related discussion

                3. Context must reference surrounding statements if relevant.

                ================ OPEN QUESTION EXTRACTION RULES ================

                1. Extract OPEN QUESTIONS when:
                - someone explicitly asks a question
                - or an issue remains unresolved

                2. Each open question MUST include:
                - question: short question text
                - evidence: exact quote with timestamp
                - context: explanation of surrounding discussion and involved people

                3. Do NOT include questions that are fully resolved.

                ================ FOLLOW-UP EMAIL EXTRACTION RULES ================

                1. Draft one email per action owner.

                2. Each email MUST include:
                - email_id_to: recipient email from people directory
                - to: recipient full name (no role)
                - subject: short professional subject
                - body: professional message including:
                    - greeting
                    - what is needed
                    - expected timing if mentioned
                    - sender name (owner)

                3. Emails must correspond to ACTION ITEMS.

                ================ GENERAL RULES ================

                1. Use ONLY people from people directory.

                2. Do NOT invent people, tasks, decisions, risks, questions, or emails.

                ================ PEOPLE DIRECTORY (USE THIS FOR ROLES & EMAILS) ================

                {json.dumps(self.people_data, indent=2)}

                ================ TRANSCRIPT ================

                {self.transcript_text}

                ================ OUTPUT FORMAT (MUST MATCH EXACTLY) ================

                {{
                "meeting_type": "{os.path.basename(self.transcript_file_path)}",
                "action_items": [
                    {{
                    "assignee": "",
                    "description": "",
                    "owner_name": "",
                    "priority": "",
                    "evidence": "",
                    "deadline_text": "",
                    "deadline": null
                    }}
                ],
                "decisions": [
                    {{
                    "decision": "",
                    "owner_name": "",
                    "evidence": ""
                    }}
                ],
                "risks": [
                    {{
                    "risk": "",
                    "evidence": "",
                    "seviarity": "",
                    "context": ""
                    }}
                ],
                "open_questions": [
                    {{
                    "question": "",
                    "evidence": "",
                    "context": ""
                    }}
                ],
                "follow_up_emails": [
                    {{
                    "email_id_to": "",
                    "to": "",
                    "subject": "",
                    "body": ""
                    }}
                ]
                }}

                Return ONLY JSON. No extra keys. No extra text.
                """
            
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )

            raw_output = response.choices[0].message.content.strip()

            if not raw_output:
                raise ValueError("LLM returned empty response")

            json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            
            if not json_match:
                raise ValueError(f"No JSON found in LLM output:\n{raw_output}")
            json_text = json_match.group()

            try:
                extracted = json.loads(json_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON from LLM: {e}")

            self.outputs["action_items"] = extracted.get("action_items", [])
            self.outputs["decisions"] = extracted.get("decisions", [])
            self.outputs["risks"] = extracted.get("risks", [])
            self.outputs["open_questions"] = extracted.get("open_questions", [])
            self.outputs["emails"] = extracted.get("follow_up_emails", [])

        except Exception as e:
            raise RuntimeError(f"Insight extraction failed: {e}")

    # ---------- EMAIL SENDER ----------
    def trigger_emails(self):
        """
        Send follow-up emails to recipients using SMTP Gmail server.
        Validates SMTP credentials and email list, establishes a secure connection
        to Gmail's SMTP server, and sends emails with subject and body content.
        Handles errors gracefully by logging failures per email and for the overall
        email system without raising exceptions.
        Raises:
            None - Exceptions are caught and logged to console.
        """

        try:
            if not SMTP_EMAIL or not SMTP_PASSWORD:
                print("⚠️ SMTP credentials missing. Skipping emails.")
                return

            if not self.outputs.get("emails"):
                print("ℹ️ No follow-up emails to send.")
                return

            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)

            for email in self.outputs["emails"]:
                try:
                    msg = MIMEText(email.get("body", ""))
                    msg["Subject"] = email.get("subject", "Follow up")
                    msg["From"] = SMTP_EMAIL
                    msg["To"] = email.get("email_id_to")

                    server.sendmail(
                        SMTP_EMAIL,
                        [email.get("email_id_to"),],
                        msg.as_string()
                    )

                    print(f"📤 Sent email to {email.get('to')}")

                except Exception as mail_err:
                    print(f"❌ Failed sending email to {email.get('to')}: {mail_err}")

            server.quit()

        except Exception as e:
            print(f"❌ Email system failed: {e}")

    # ---------- MAIN FLOW ----------
    def start_process(self):
        """
        Start the AI processing pipeline for meeting analysis.
        Executes the following steps in sequence:
        1. Reads transcript file
        2. Reads people details file
        3. Validates compatibility between documents using LLM
        4. Identifies meeting type from filename
        5. Extracts insights from the meeting
        Returns:
            dict: Processed outputs containing analysis results, or error details if processing fails.
        Raises:
            RuntimeError: If LLM validation call fails.
            ValueError: If validation fails due to incompatible documents.
        """

        try:
            self.transcript_reader()
            self.peope_details_reader()

            # Validate compatibility
            try:
                is_valid = llm_validate_documents(self.client, self.people_data, self.transcript_text)
            except Exception as e:
                raise RuntimeError(f"Validation LLM call failed: {e}")

            if not is_valid:
                raise ValueError("Validation failed: people file and transcript are not compatible.")

            self.identify_meeting_type_from_filename()
            self.extract_insights()
            # self.trigger_emails() # enable this before run to trigger email

            return self.outputs

        except Exception as e:
            print("❌ AI_AGENT PROCESS FAILED")
            print(e)
            return {
                "error": str(e),
                "outputs": self.outputs
            }
