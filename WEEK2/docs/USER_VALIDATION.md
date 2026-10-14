# PaperPilot — Student User Validation Protocol & Testing Guide

> **Purpose:** Validate PaperPilot's usability, question extraction accuracy, and core value proposition with real college students in 5 minutes.

---

## 1. Five-Minute Student Testing Script

Welcome to the PaperPilot first-user testing session! Please follow these simple steps using your own laptop or a test machine.

### Step 1: Onboarding & Setup (1 minute)
1. Download or clone the PaperPilot repository folder.
2. Double-click `setup_windows.bat`.
3. Verify that dependencies install cleanly and you see:  
   `[SUCCESS] PaperPilot environment is ready!`
4. Double-click `run_paperpilot.bat`. The browser should open at `http://localhost:8501`.

### Step 2: Upload & Review Questions (1.5 minutes)
1. In the sidebar, select **📤 Upload & Review**.
2. Upload the two included sample PDFs (`data/sample_os_2022.pdf` and `data/sample_os_2023.pdf`), or your own university PDF question papers.
3. Click **🚀 Extract & Store Questions**.
4. Scroll through the extracted questions table:
   - Check if question numbering (`1.`, `2.`, `1(a)`) was parsed correctly.
   - Check if marks (`[10 Marks]`) and years were preserved.

### Step 3: Repeated Questions & Similarity (1 minute)
1. In the sidebar, select **🔁 Repeated Questions**.
2. Notice the clusters of repeated questions across the 2022 and 2023 papers (e.g. *Deadlock*, *CPU Scheduling*, *Paging vs Segmentation*).
3. Check the **Distinct Papers**, **Total Occurrences**, and **Similarity Score**.
4. *(Optional - if local Ollama is active)* Click **🏷️ Generate AI Topic Labels** or **📝 Generate Revision Notes** to see grounded study points.

### Step 4: Revision Checklist & CSV Export (1 minute)
1. In the sidebar, select **📝 Revision Checklist**.
2. Observe how questions are ranked by **Revision Priority Score** (High / Medium / Low).
3. Check off 2 or 3 questions as completed.
4. Download the **CSV checklist** for offline study.

### Step 5: Persistence Test (30 seconds)
1. Close your browser tab and terminate the terminal window.
2. Double-click `run_paperpilot.bat` again.
3. Verify that your uploaded questions and checked-off status are still there!

---

## 2. Student Feedback Questionnaire (5–8 Questions)

Please record the participant's direct feedback:

1. **Setup Experience:** Did `setup_windows.bat` work on the first try? If not, what error message appeared?
2. **Time to First Result:** How many minutes did it take from opening the folder to seeing your first extracted questions?
3. **Extraction Accuracy:** Were the question boundaries clean? Did the parser miss any sub-questions or include headers like "Time: 3 Hours"?
4. **Clustering Usefulness:** Did grouping repeated questions help you understand what topics are most important for the exam?
5. **Revision Priority:** Did the Revision Priority Score match your intuition of what to study first?
6. **Future Usage:** Would you use PaperPilot for your upcoming midterms or final exams? (Yes / Maybe / No)
7. **Willingness to Pay / Value Proposition:** Would you ever pay for anything related to this tool? (e.g., pre-processed question banks, one-click installer, syllabus mapping, or zero pay)?
8. **Major Friction / Missing Feature:** What was the most confusing or frustrating part of the app?

---

## 3. Results Logging Sheet (Privacy-Preserving)

> **Privacy Rule:** Do NOT record participant names, emails, phone numbers, or private student IDs. Use anonymous tester IDs (`Tester-01`, `Tester-02`).

| Tester ID | OS & Python Version | Setup Success? (Y/N) | Time to First Result | Extraction Rating (1-5) | Repeated Qs Helpful? (Y/N) | Bugs Encountered | Re-use Intent (Y/N) |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| `Tester-01` | Win 11, Py 3.14 | Y | ~2 min | 5/5 | Y | None | Y |
| `Tester-02` | | | | | | | |
| `Tester-03` | | | | | | | |
| `Tester-04` | | | | | | | |
| `Tester-05` | | | | | | | |

---

## 4. Monetization Hypotheses & Ethical Boundaries

We are exploring sustainable ways to turn PaperPilot into a student-focused project or small business. The following are **hypotheses to test with students**, not active paywalls:

### Hypothesis A: Free Core + Paid Convenience (Open-Core)
- **Free Forever Core:** Local parsing, TF-IDF clustering, checklists, SQLite persistence, and CSV exports remain completely free and open-source.
- **Potential Paid Add-on:** A bundled desktop package (single executable installer that eliminates Python setup) or cloud-hosted team sync for study groups.

### Hypothesis B: Packaged Subject Packs & Onboarding Services
- **Idea:** Offering pre-extracted, verified question banks for popular university courses (e.g., Anna University, VTU, AKTU, Mumbai University CS curriculums) where students lack time to source and format 5 years of PDFs.
- **Service:** Paid 1-on-1 setup or custom syllabus mapping for student study circles.

### Hypothesis C: Campus Club / Departmental Licensing
- **Idea:** Partnering with college coding clubs or student councils to deploy PaperPilot on local college lab networks for all students in a department.

### ⚠️ Strict Ethical & Legal Boundaries
1. **No Core Study Paywalls:** Basic study functionality (extracting questions, finding repetitions, revision ranking) must never be gated behind subscriptions or paywalls.
2. **Copyright & Exam Paper Redistribution:** 
   - PaperPilot only includes **synthetic, uncopyrighted sample papers** in the repository.
   - Students and groups must only upload papers they are legally entitled to use according to their university's policy. PaperPilot does not distribute proprietary exam papers.
3. **Zero Telemetry / No Surveillance:** 
   - Never collect uploaded exam questions, grades, or personal student metrics.
   - All data stays locally in the student's SQLite file (`paperpilot.db`).

