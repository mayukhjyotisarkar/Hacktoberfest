"""
generate_samples.py - Generates synthetic sample question papers for offline testing.
"""

from pathlib import Path
import pymupdf

DATA_DIR = Path(__file__).parent


def create_os_2022_pdf():
    doc = pymupdf.open()
    page1 = doc.new_page()
    content = (
        "B.TECH SEMESTER EXAMINATION - 2022\n"
        "Department of Computer Science & Engineering\n"
        "Subject: Operating Systems (CS-401)\n"
        "Time: 3 Hours                  Max. Marks: 100\n"
        "---------------------------------------------------\n"
        "Note: Answer any five questions.\n\n"
        "1. What is an Operating System? Explain its main functions and types. [10 Marks]\n\n"
        "2. Explain process state transitions with a neat diagram. What information is stored in a PCB? [10 Marks]\n\n"
        "3. Define CPU scheduling. Compare FCFS, Round Robin, and SJF scheduling algorithms with an example. [15 Marks]\n\n"
        "4. What is a Deadlock? Explain the four necessary conditions for deadlock occurrence. [10 Marks]\n\n"
        "5. Explain the concept of Virtual Memory. What is demand paging? [10 Marks]\n\n"
        "6. Differentiate between paging and segmentation with suitable diagrams. [15 Marks]\n\n"
        "7. Write short notes on: (a) Thrashing  (b) Semaphore  (c) Critical Section Problem. [15 Marks]\n"
    )
    page1.insert_text((40, 50), content, fontsize=10)
    out_path = DATA_DIR / "sample_os_2022.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def create_os_2023_pdf():
    doc = pymupdf.open()
    page1 = doc.new_page()
    content = (
        "B.TECH SEMESTER EXAMINATION - 2023\n"
        "Department of Computer Science & Engineering\n"
        "Subject: Operating Systems (CS-401)\n"
        "Time: 3 Hours                  Max. Marks: 100\n"
        "---------------------------------------------------\n"
        "Instructions: All questions carry equal marks.\n\n"
        "1. Define Operating System. Discuss the dual-mode operation in modern operating systems. [10 Marks]\n\n"
        "2. What is a Process Control Block (PCB)? Explain process states with a state transition diagram. [10 Marks]\n\n"
        "3. Explain Deadlock. Discuss the necessary conditions for a deadlock to occur in a system. [10 Marks]\n\n"
        "4. What is CPU scheduling? Differentiate between preemptive and non-preemptive scheduling. [10 Marks]\n\n"
        "5. Explain the differences between Paging and Segmentation memory management techniques. [15 Marks]\n\n"
        "6. Describe Bankers Algorithm for deadlock avoidance with a clear illustrative example. [15 Marks]\n\n"
        "7. Explain Page Fault and Page Replacement algorithms: FIFO, LRU, and Optimal. [15 Marks]\n"
    )
    page1.insert_text((40, 50), content, fontsize=10)
    out_path = DATA_DIR / "sample_os_2023.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    create_os_2022_pdf()
    create_os_2023_pdf()

