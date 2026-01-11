# siva-krishna-intellentech-assessment

---------------- AI MEETING INTELLIGENCE AGENT -----------------

This project is an autonomous AI agent that analyzes meeting transcripts and extracts structured meeting outcomes such as Action Items, Decisions, Risks, Open Questions, and Follow-up Emails using an LLM.

It helps convert meeting discussions into clear responsibilities and next steps automatically.

---------------- FEATURES -----------------

-Reads meeting transcript from text file
-Reads people directory with roles and email IDs from JSON
-Validates transcript and people data using LLM

Extracts:
Action Items with Owner and Assignee
Decisions made during meeting
Risks and blockers
Open questions
Generates follow-up emails for action owners
Sends emails using SMTP

---------------- SETUP INSTRUCTIONS -----------------

1.Clone Repository
git clone <repository-ssh-url>
cd <project-folder>

2.Create Virtual Environment
python -m venv venv
venv\Scripts\activate

3.Install Dependencies
pip install -r requirements.txt

4.Create .env File
add :
GROQ_API_KEY=your_groq_api_key
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password

---------------- EXCECUTION INSTRUCTIONS --------------

-After completing the Setup active the environment
-Enter into Environment folder
-Add input files in this input_data folder and update the file names in main.py file
-Now run main.py file from it's path (python main.py)
-To send follow up emails need to enable trigger_emails() in ai_engine.py file in line 425
-Output is file will be generate and stored in outputs folder with file name MEETING_TYPE_YYYY_MM_DD.json

---------------- ASSUMPTIONS ------------------------

1.Transcript file naming convention must follow the format:
MEETING_TYPE.txt
Example: sprint_planning.txt, product_sync.txt

2.Only one unique meeting type is conducted per day.
Since the output file is generated using only the meeting type and date
(MEETING_TYPE_YYYY_MM_DD.json), multiple meetings of the same type on the
same day will overwrite the previous output.

---------------- WORKFLOW ---------------------------

-Load transcript file
-Load people directory
-Validate data compatibility using LLM (as guardrail)
-Send prompt to LLM
-Extract structured information
-Generate and send emails

---------------- AUTHOR ------------------------------
Siva Krishna Repani
