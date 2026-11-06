"""
Build the FORGE-Vision video-presentation voiceover script as a .docx.

Output: presentation/Forge-Vision_Presentation_Script.docx

Style:
  - Heading 1 per page / major part
  - Heading 2 per tab / section
  - Normal paragraphs = the words to READ ALOUD (voiceover)
  - "On screen" cues = italic grey paragraphs prefixed "▶ On screen:"
Run:  cd presentation && python build_script_docx.py
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

GOLD = RGBColor(0xB8, 0x86, 0x0B)     # dark gold (prints well)
INK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x66, 0x66, 0x66)
BLUE = RGBColor(0x1F, 0x4E, 0x79)

doc = Document()

# Base style
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11.5)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.18

for lvl, sz, col in [("Heading 1", 17, GOLD), ("Heading 2", 13.5, BLUE), ("Heading 3", 12, INK)]:
    s = doc.styles[lvl]
    s.font.name = "Calibri"
    s.font.size = Pt(sz)
    s.font.color.rgb = col
    s.font.bold = True


def h1(t):
    doc.add_heading(t, level=1)

def h2(t):
    doc.add_heading(t, level=2)

def h3(t):
    doc.add_heading(t, level=3)

def cue(t):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("▶ On screen: " + t)
    r.italic = True
    r.font.color.rgb = GREY
    r.font.size = Pt(10.5)

def say(t):
    p = doc.add_paragraph(t)
    return p

def note(t):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.italic = True
    r.font.color.rgb = GREY
    r.font.size = Pt(10)

def rule():
    p = doc.add_paragraph()
    p.add_run("— — —").font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


# ══════════════════════════ COVER ══════════════════════════
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("FORGE-VISION")
r.bold = True; r.font.size = Pt(34); r.font.color.rgb = GOLD
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Video Presentation — Voiceover Script")
r.font.size = Pt(15); r.font.color.rgb = INK
sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub2.add_run("A Hybrid Computer-Vision & Generative-AI System for Employee Training")
r.italic = True; r.font.color.rgb = GREY
sub3 = doc.add_paragraph()
sub3.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub3.add_run("Presented by Mashkur Alam · Prof. Dr. Karim Mohammed Rezaul (DBA)")

doc.add_paragraph()
note("How to use this script: read the normal text aloud as your voiceover. The grey "
     "\"▶ On screen\" lines tell you what to click or show at that moment — they are NOT read aloud. "
     "Record as the Admin account so every page and tab is visible. Parts 1 and 3 are the intro / "
     "conclusion slide decks (intro_slides.html / outro_slides.html); Part 2 is the live app walkthrough.")
doc.add_page_break()


# ══════════════════════════ PART 1 — INTRO SLIDES ══════════════════════════
h1("PART 1 — Introduction (Slides)")
note("Present intro_slides.html full-screen. One slide per heading below; read the narration over it.")

h2("Slide 1 — Title")
cue("Title slide: FORGE-Vision.")
say("Good day, and welcome. My name is Mashkur Alam, and this is FORGE-Vision — a hybrid "
    "computer-vision and generative-AI system for employee training, developed as the applied "
    "artefact of a Doctor of Business Administration research project. In this presentation I'll "
    "explain what the system is, how it works, and then take you on a complete tour of the live "
    "platform — every screen, from login to logout.")

h2("Slide 2 — What it is")
cue("\"What it is\" slide.")
say("At its core, FORGE-Vision watches a worker perform a task through an ordinary camera, "
    "compares what they're doing against the approved Standard Operating Procedure — the SOP — "
    "and the moment it detects a deviation, it generates instant, plain-language corrective "
    "guidance that explains what went wrong and why. In short: it's a real-time, AI-powered "
    "training coach that never blinks.")

h2("Slide 3 — The problem")
cue("\"The problem\" slide.")
say("The problem it solves is one of timing. In most workplaces, a large share of error comes "
    "not from a lack of knowledge, but from small deviations during execution. Traditional "
    "training is retrospective — feedback arrives hours or days later, long after the moment of "
    "the mistake, when its teaching value has faded. FORGE-Vision closes that gap by delivering "
    "feedback in the moment, specific to the exact step the worker is on.")

h2("Slide 4 — How it works")
cue("\"How it works\" slide — the four-layer pipeline.")
say("It works as a four-layer pipeline. First, perception: OpenCV processes each video frame, "
    "MediaPipe tracks the worker's body pose, and a YOLO detector spots the tools and protective "
    "equipment. Second, recognition: a compact deep-learning model — MobileNet plus an LSTM — "
    "classifies the action, at around eighty-six percent accuracy and sixty-two milliseconds per "
    "frame. Third, intelligence: a deviation detector compares the action against the SOP and, on "
    "a mismatch, asks a large language model to write the correction. And fourth, guidance: that "
    "explainable feedback reaches the worker in under two seconds.")

h2("Slide 5 — System architecture")
cue("\"System architecture\" slide — the diagram.")
say("Architecturally, everything runs through a single secure entry point. The browser connects "
    "over HTTPS to a Caddy reverse proxy, which routes data to a FastAPI backend — that's the "
    "brain, exposing both a REST API and a live WebSocket for the camera. The backend talks to a "
    "PostgreSQL database for all records, and the interface you'll see is built in Streamlit. "
    "The whole system is containerised with Docker and runs, completely free, in the cloud on a "
    "Hugging Face Space backed by a Supabase database.")

h2("Slide 6 — Components used")
cue("\"Components\" slide — frontend / backend / database / CV / LLM.")
say("To put names to the parts: the front end is Streamlit, with a React option for the future. "
    "The back end is FastAPI with asynchronous SQLAlchemy and Pydantic for validation. The "
    "database is PostgreSQL. The computer-vision stack is OpenCV, MediaPipe, YOLOv8 and PyTorch. "
    "And the language model is pluggable — Groq, OpenAI, Anthropic, Gemini, or a fully local "
    "Ollama — so the system is never locked to one vendor.")

h2("Slide 7 — Let's see it live")
cue("\"Let's see it live\" hand-off slide, then switch to the live app.")
say("That's the idea. Now let's see it working — this is the real, deployed system.")
doc.add_page_break()


# ══════════════════════════ PART 2 — APP WALKTHROUGH ══════════════════════════
h1("PART 2 — Live Application Walkthrough")
note("Recorded as Admin so every group and tab is reachable. Order follows a natural top-to-bottom tour.")

# ---- A. Login ----
h2("A. Login")
cue("The login page — split screen: gold brand panel on the left, sign-in form on the right.")
say("This is the front door. On the left is the FORGE-Vision brand panel; on the right, the "
    "sign-in form. Access is controlled, because the system handles workplace performance data.")
cue("Point to the Email and Password fields.")
say("I enter my email address and password — credentials are encrypted in transit, and the "
    "footer confirms the platform is GDPR-compliant and AES-256 encrypted.")
cue("Click 'SIGN IN →'.")
say("And I sign in. If an account has two-factor authentication enabled, a six-digit code from "
    "an authenticator app is requested here as a second step — an extra layer of security for "
    "sensitive roles.")

# ---- B. Topbar ----
h2("B. The Top Bar (always visible)")
cue("Gesture across the top bar after the dashboard loads.")
say("Before we explore, two areas stay with us on every screen. Across the top is the bar that "
    "shows the current page name on the left, and the account controls on the right.")
cue("Point to the 'View as' dropdown.")
say("Because I'm signed in as an administrator, I get a special control here — 'View as'. This "
    "lets me preview the system exactly as a Staff member, a Trainer, or a Manager would see it, "
    "with their restricted menus. It's invaluable for support and for designing role-appropriate "
    "training.")
cue("Point to the profile badge, then Help, then Sign Out.")
say("Next to it is my profile badge showing my role, a Help button that opens the documentation, "
    "and the Sign Out button, which we'll use right at the end.")

# ---- C. Sidebar ----
h2("C. The Sidebar Navigation (always visible)")
cue("Gesture down the left sidebar; expand each group.")
say("Down the left is the main navigation. It's deliberately organised into logical groups so "
    "the platform never feels overwhelming. Dashboard sits pinned at the top. Below it: the "
    "Training group, the Data and Analytics group, the Administration group — which only "
    "administrators see — and the Account group. What appears here adapts to your role; as an "
    "admin, I see everything. Let's go through each, starting with the Dashboard.")

# ---- D. Dashboard ----
h2("D. Dashboard")
cue("The Dashboard loads.")
say("This is the operations dashboard — the command centre. Everything on it is live data, "
    "queried straight from the database; there's no mock content.")
cue("Point to the three quick-action buttons at the top.")
say("At the very top are three shortcuts to the most common actions: Start Session, which jumps "
    "straight into live training; New SOP, to author a procedure; and Reports, to generate one.")
cue("Hover the System Status panel (the three cards).")
say("On the left, the System Status panel is a live heartbeat of the three critical services — "
    "the API backend, the PostgreSQL database with its current query time, and the active "
    "language-model provider. If anything degrades, it shows here first.")
cue("Point to the four metric tiles.")
say("Beneath it, four headline figures summarise the whole programme: sessions running right "
    "now, total sessions ever conducted, total deviations detected, and how many of those were "
    "high-severity.")
cue("Hover the Live Activity Feed entries on the right.")
say("The centre of the page is the Live Activity Feed. Each entry is a training session, "
    "colour-coded by severity — green, amber, or red — showing the worker, the procedure, when "
    "it ended, and key numbers including the inference latency, which is the system holding "
    "itself to its real-time promise.")
cue("Scroll to the Recent Sessions table.")
say("And below that, the Recent Sessions table gives the same information in a clean tabular "
    "form, with each worker's name, their score, the duration, and a status tick.")

# ---- E. Training ----
h1("Training Group")
note("Sidebar → expand 'Training'.")

h2("E1a. Live Training — a clean run")
note("Record this as a SILENT screen capture of a run with NO skips (complete every step). → live_clean.mp4")
cue("Open Training → Live Training.")
say("This is the centrepiece of the platform — and we'll see it twice: first with a worker who "
    "does everything right, then with one who makes mistakes, so the difference is plain. Notice "
    "the first thing shown is not a camera but a privacy notice: video is processed in memory only, "
    "never stored, and only session metadata is saved. Consent is explicit and required.")
cue("Tick the consent checkbox.")
say("I confirm consent to continue.")
cue("Point to the two-column layout — SOP preview on the left, Session Setup on the right — then Start.")
say("On the left is a preview of the procedure: its ordered steps, the required protective "
    "equipment, and any safety-critical steps flagged in red. On the right, the Session Setup card. "
    "I pick a procedure and press Start Session — and we go live.")
cue("Point to the live metrics bar, the per-step and total timers, and the live camera panel.")
say("A live metrics bar appears — a pulsing LIVE indicator, a running timer, the current step with "
    "a progress bar, and a deviation counter. Each step carries its own countdown beside the total "
    "elapsed time. On the right, the live camera: the worker's own webcam streams to the server, "
    "which draws the pose skeleton and labels the detected tools right on the video.")
cue("Mark each step Complete, in order, all the way through.")
say("In this first run the worker performs every step correctly — marking each one complete and "
    "moving cleanly through the whole procedure.")
cue("Finish to the Session Summary (clean run — point to the '🧠 AI Coaching' note).")
say("And here is the result: a full score, every step completed, none skipped. The AI Coaching "
    "panel simply confirms a clean run — no corrections needed. The system recognises good practice "
    "and says so. Now, let's see what happens when things go wrong.")

h2("E1b. Live Training — when things go wrong (AI coaching)")
note("Record this as a SILENT screen capture of a run WITH 2–3 skips (and/or one timeout). → live_skip.mp4")
cue("Start a second session of the same procedure.")
say("Same worker, same procedure — but this time, mistakes. We'll skip required steps and let the "
    "clock run out on another: exactly the kind of deviation from the Standard Operating Procedure "
    "that the system exists to catch.")
cue("Skip 2–3 steps (give a reason each time), and/or let one step run past its time limit.")
say("Here the worker skips a required step, giving a reason for the record; skips another; and lets "
    "a third run past its time limit. Each is captured, the moment it happens, as a deviation — a "
    "missing step, an over-time step.")
cue("Finish to the Session Summary — point to each card in the '🧠 AI Coaching & Feedback' section.")
say("And now the difference is unmistakable. Where the clean run earned a simple confirmation, this "
    "run earns the AI's coaching for every single deviation. For each mistake, FORGE-Vision presents "
    "a specific, plain-language correction — exactly what went wrong on that step, and how to put it "
    "right. This is generative AI made tangible: not a generic warning, but tailored guidance for "
    "each error, the moment the session ends. The session and its coaching are saved to the research "
    "database, so the same feedback is available afterwards in Session History. That contrast — "
    "confirming what is done well, and coaching what is not — is the very heart of FORGE-Vision.")

h2("E2. Simulation — the research instrument")
cue("Open Training → Simulation.")
say("Where Live Training is the experience, the Simulation page is the science. Notice the "
    "banner: all data here is clearly labelled synthetic, generated from published baselines, "
    "because real-participant data requires ethics approval — academic integrity made visible.")
cue("Point to the Experiment Configuration inputs.")
say("At the top, the experiment is fully configurable: participants per group, the significance "
    "level alpha, the target statistical power, the expected effect size, and a fixed random "
    "seed for reproducibility.")
cue("Point to the Power Analysis metrics.")
say("A power-analysis panel confirms whether the sample is adequately powered to detect an "
    "effect.")
cue("Click through the three 'Synthetic Group Distributions' sub-tabs.")
say("These three sub-tabs visualise the outcomes across the study groups: Errors per Task, "
    "Completion Time, and Sessions to Competency — each as a box-plot comparison.")
cue("Click 'Run Hypothesis Tests', then open the H1 / H2 / H3 result panels.")
say("And here is the formal evaluation. Running the tests produces results for the three "
    "research hypotheses. Each opens to show the p-value, the effect size — Cohen's d or "
    "eta-squared — the group means with confidence intervals, post-hoc comparisons, and, "
    "importantly, the assumption checks behind every test. A defensible result must show its "
    "assumptions were examined, not assumed.")
cue("Scroll to the overall verdict and the Download JSON button.")
say("An overall verdict summarises whether all three hypotheses are supported, and the entire "
    "experiment record can be exported as JSON.")
cue("Scroll to the Continual Learning panel.")
say("Finally, the Continual Learning panel. Using a technique called Elastic Weight "
    "Consolidation, the model can learn from new data without forgetting what it already knew. "
    "An administrator sets the parameters and runs an incremental learning job; the results "
    "table shows the retention rate and the accuracy before and after.")

h2("E3. Create SOP")
cue("Open Training → Create SOP.")
say("This is where the procedures themselves are authored — and the system's intelligence is "
    "only as good as the SOP it judges against.")
cue("Point to the Mode toggle: Create New vs Upload Document.")
say("There are two modes. 'Create New' builds a procedure from scratch; 'Upload Document' takes "
    "an existing written procedure and has a language model parse it into structured form "
    "automatically.")
cue("In Create New, point to the metadata fields.")
say("In Create New, I first define the metadata: a unique ID, a readable name, a version, a "
    "category, a department, an estimated duration, and the required protective equipment.")
cue("Point to the Steps builder and the Add Step button.")
say("Then I build the steps. Each step has a name, a description, the objects and pose it "
    "expects, a time limit, a safety-critical flag, and its own equipment list — and steps can "
    "be reordered or removed. Add Step inserts a new one.")
cue("Click 'Preview YAML', then 'Save SOP'.")
say("Preview YAML shows the machine-readable definition that results, and Save commits it to "
    "the library.")
cue("Switch to Upload Document mode and point to the file uploader + Parse button.")
say("In Upload Document mode, I simply drop in a text, PDF or Word file and click Parse and "
    "Populate — the language model reads it and fills in the steps for me.")

# ---- F. Data & Analytics ----
h1("Data & Analytics Group")
note("Sidebar → expand 'Data & Analytics'.")

h2("F1. Session History")
cue("Open Data & Analytics → Session History.")
say("Session History is the forensic record of every training session.")
cue("Point to the filters and the Search button.")
say("I can filter by worker, by procedure, and by date range, then Search.")
cue("Point to the KPI tiles and the session table.")
say("Summary tiles sit above a table of matching sessions, with their scores, durations and "
    "deviation counts.")
cue("Open the Deviation Drill-Down and select a session.")
say("And the most powerful part — the Deviation Drill-Down. I pick any session and the system "
    "lists every individual deviation it recorded: its class, its severity, the exact step it "
    "happened on, and the what and the why. This is the granular evidence beneath the aggregates.")
cue("Point to pagination and the Download CSV button.")
say("Results are paginated, and the whole filtered set can be exported to CSV.")

h2("F2. Staff Profiles")
cue("Open Data & Analytics → Staff Profiles.")
say("Staff Profiles turns sessions into a per-worker development record.")
cue("Search a worker, then select one to open Profile Detail.")
say("I search for a worker and open their profile. It shows their session count, deviation "
    "history, high-severity events, and a derived skill level.")
cue("Point to the editable fields and Update Profile.")
say("A trainer can edit the skill level, department, employee ID and add private trainer notes, "
    "then save with Update Profile.")
cue("Expand the recent-sessions section.")
say("And an expandable panel lists that worker's recent sessions for quick context.")

h2("F3. SOP Library")
cue("Open Data & Analytics → SOP Library.")
say("The SOP Library is the catalogue of every approved procedure — here, twenty-two of them, "
    "spanning data science, security, laboratory safety, food hygiene and emergency response.")
cue("Point to a few SOP cards, then the search box and New SOP button.")
say("Each card shows the category, the owning department, the number of steps and the expected "
    "duration. I can search the library, or create a new procedure.")
cue("Click 'View Details' on one SOP.")
say("View Details opens the full definition — every step expandable to show its objects, its "
    "ordering dependencies, its time limit, its equipment and any safety flag. Administrators "
    "can also delete a procedure here.")

h2("F4. Analytics")
cue("Open Data & Analytics → Analytics.")
say("The Analytics page is where the raw data becomes insight. Six headline metrics sit at the "
    "top — total sessions, total deviations, high-severity events, active workers, average "
    "latency, and the latency-target pass rate, which is above ninety-nine percent, proving the "
    "two-second promise holds at scale. Below them are seven tabs, each a different lens.")
cue("Open the 'Session History' tab.")
say("The first tab, Session History, is a filterable, paginated table of all sessions.")
cue("Open the 'Worker Performance' tab; load a worker.")
say("Worker Performance profiles an individual — their skill level, an improvement rate "
    "comparing early and recent sessions, an estimate of sessions to competency, and a chart of "
    "their deviation trend over time.")
cue("Open the 'SOP Analytics' tab; load an SOP.")
say("SOP Analytics flips the view to a procedure — ranking its most problematic steps and "
    "showing the distribution of deviation types.")
cue("Open the 'Deviation Heatmap' tab.")
say("The Deviation Heatmap cross-tabulates deviation class against severity, so the riskiest "
    "combinations stand out at a glance.")
cue("Open the 'Study Groups' tab.")
say("Study Groups is built for the research. It divides the cohort into the four experimental "
    "arms — control, simulation-only, real-time-only, and hybrid — and compares their accuracy "
    "and deviations, with learning curves over successive sessions. The hybrid group's clear "
    "lead is the visual signature of the study's central finding.")
cue("Open the 'Emotion Breakdown' tab.")
say("Emotion Breakdown analyses engagement states — focused, neutral, stressed, fatigued — "
    "from facial-expression analysis, recognising that wellbeing and learning are linked.")
cue("Open the 'Bias Audit' tab.")
say("And Bias Audit checks fairness, comparing accuracy across departments against the cohort "
    "average and flagging any group that falls significantly behind — a responsible-AI "
    "safeguard.")

h2("F5. Reports")
cue("Open Data & Analytics → Reports.")
say("The Reports page is for dissemination and the thesis itself.")
cue("Set the date range and Workers / SOPs filters, then click 'Generate Report'.")
say("I choose a date range and, optionally, specific workers or procedures, then Generate "
    "Report.")
cue("Point to the KPI cards and the two charts.")
say("It produces headline cards — total sessions, average accuracy, deviations, the top "
    "performer, and the single most-deviated step — alongside charts of deviations by worker "
    "and accuracy over time.")
cue("Point to the Deviation Breakdown section.")
say("A deviation breakdown splits events into low, medium and high severity.")
cue("Point to the Export CSV and Export PDF buttons.")
say("And the whole thing exports to a publication-ready PDF, or to CSV for further analysis.")

h2("F6. Leaderboard")
cue("Open Data & Analytics → Leaderboard.")
say("The Leaderboard adds a motivational layer.")
cue("Point to the Period, Study group and Department filters.")
say("I can rank by this week, this month or all time, and filter by study group or department.")
cue("Point to the rankings table and the badges.")
say("The rankings use the same severity-weighted accuracy as everywhere else — so it rewards "
    "safe, correct work, not just speed — with medals for the top three and achievement badges "
    "like Zero Error Day and Safety First.")
cue("Point to 'My Standing' and the Top-5 trend chart.")
say("A 'My Standing' panel shows an individual where they sit and how far behind the leader they "
    "are, and a trend chart tracks the top five performers over time.")

# ---- G. Administration ----
h1("Administration Group")
note("Sidebar → expand 'Administration' (admin-only).")

h2("G1. Settings")
cue("Open Administration → Settings.")
say("Settings is where an administrator connects the AI model that powers all the feedback.")
cue("Point to the active-configuration banner and saved configs.")
say("The banner shows the currently active provider and model, and any saved configurations can "
    "be switched between with a click.")
cue("Point to the provider cards.")
say("The system supports six providers — Groq, Gemini, OpenAI, Anthropic, xAI and a fully local "
    "Ollama — each labelled free, paid or local.")
cue("Select a provider; point to the model dropdown and API key field.")
say("Choosing one reveals its configuration: the model to use, and an API key, which is stored "
    "encrypted in the database — never in code. For Ollama, it fetches the locally installed "
    "models instead.")
cue("Point to 'Test Connection' and 'Save Settings'.")
say("Test Connection verifies the provider live and records its response time; Save Settings "
    "makes it active for all feedback generation.")
cue("Scroll to the Feedback Demo.")
say("And there's a neat Feedback Demo at the bottom: pick a deviation type and a procedure, and "
    "it shows, side by side, the basic rule-based message versus the richer language-model "
    "feedback — making the value of the AI immediately tangible.")

h2("G2. User Management")
cue("Open Administration → User Management.")
say("User Management is full role-based access control.")
cue("Click 'Add New User'; point to the Create User and Invite-by-email tabs.")
say("I can add a user directly — entering their name, email, department, role and password — or "
    "invite them by email. Every account carries a role: staff, trainer, manager or admin, which "
    "governs exactly what they can see and do.")
cue("Point to the search and Role / Status filters, then the user table.")
say("The user list can be searched and filtered by role or status, and the table shows each "
    "account's ID, name, email, role, session count and last activity.")
cue("Point to the edit (✏️) and delete (🗑️) actions and the Export CSV button.")
say("From each row I can edit a user or, with a confirmation step, delete one — and the whole "
    "list exports to CSV. Crucially, this enforcement is server-side, not just hidden in the "
    "interface.")

h2("G3. System Health")
cue("Open Administration → System Health.")
say("System Health is the live operations view.")
cue("Point to the service cards and the auto-refresh toggle.")
say("It shows the real-time status of the API with its uptime, the database with its query "
    "time, and the language-model provider, refreshing automatically every thirty seconds.")
cue("Point to the five metric tiles.")
say("Five tiles summarise the system's footprint — active sessions, procedures, sessions, "
    "deviations and users.")
cue("Point to the LLM Latency History chart.")
say("And a chart tracks the language model's response time over the session, so the team can "
    "watch the responsiveness that underpins the real-time guarantee.")

h2("G4. Audit Log")
cue("Open Administration → Audit Log.")
say("Finally in this group, the Audit Log. Every consequential action — a login, a settings "
    "change, a user edit, a procedure saved — is recorded here, searchable and paginated, "
    "showing who did what, to what, and when. For a system that processes performance data, this "
    "accountability trail is both a security control and an ethics requirement, and it exports "
    "in full to CSV.")

# ---- H. Account ----
h1("Account Group")
note("Sidebar → expand 'Account'.")

h2("H1. Notifications")
cue("Open Account → Notifications.")
say("Notifications surface system events — a completed training run, a newly available "
    "procedure, a health alert — grouped by day, with an unread count.")
cue("Point to a notification and the mark-read tick, then 'Mark all read'.")
say("Each can be marked read individually, or all at once.")

h2("H2. My Account")
cue("Open Account → My Account.")
say("My Account is each user's own profile and security hub.")
cue("Point to the profile card and 'Edit Profile'.")
say("It shows their ID, role, session count and membership date, and lets them edit their name "
    "and email.")
cue("Point to 'Change Password'.")
say("They can change their password here too.")
cue("Point to the GDPR section and 'Request Account Deletion'.")
say("And, in line with GDPR, there's a clear data-rights section — including the ability to "
    "request account deletion, which flags the account for erasure within thirty days. For an "
    "administrator, this page also offers an Account Lookup panel to assist any user by ID or "
    "email.")

# ---- I. Help ----
h1("Help")
cue("Click 'Help' in the top bar.")
say("The Help button, in the top bar, opens the built-in documentation — organised into six "
    "tabs.")
cue("Click through the six Help tabs as they're named.")
say("Getting Started gives a guided first-run checklist. API Reference lists the key endpoints "
    "for developers. SOP Guide documents the procedure format. Troubleshooting answers common "
    "issues like camera or model problems. About describes the project, its version and its "
    "research hypotheses. And Data and Privacy sets out the full GDPR position — your rights, the "
    "data-retention schedule, and who to contact.")

# ---- J. Logout ----
h1("Logout")
cue("Click 'Sign Out' in the top bar.")
say("And that completes the tour. To finish, I sign out from the top bar — which clears the "
    "session securely and returns to a clean signed-out confirmation. That's the entire platform, "
    "from the front door to the last click.")
doc.add_page_break()


# ══════════════════════════ PART 3 — CONCLUSION SLIDES ══════════════════════════
h1("PART 3 — Conclusion (Slides)")
note("Present outro_slides.html full-screen; read the narration over it.")

h2("Slide 1 — What we saw")
cue("\"What we saw\" slide.")
say("So, what have we seen? A single platform that takes a worker through a procedure, detects "
    "deviations live, explains them in plain language within two seconds, and then records, "
    "analyses and evaluates every session as rigorous research data.")

h2("Slide 2 — Results")
cue("\"Results\" slide.")
say("And the evidence is encouraging. On the study data, all three research hypotheses are "
    "supported at conventional significance levels; the recognition model reaches around "
    "eighty-six percent accuracy; and the entire system runs live, in the cloud, at no cost.")

h2("Slide 3 — Contribution & thank you")
cue("\"Contribution / Thank you\" closing slide.")
say("FORGE-Vision demonstrates that real-time, explainable, AI-generated guidance can be "
    "delivered on everyday hardware — and that the resulting platform is also a powerful "
    "instrument for testing how people learn. My name is Mashkur Alam. Thank you for watching, "
    "and I welcome your questions.")

doc.save("Forge-Vision_Presentation_Script.docx")
print("Saved Forge-Vision_Presentation_Script.docx")
