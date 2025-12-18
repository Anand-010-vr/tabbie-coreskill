import os
import re
import json
from pathlib import Path
from typing import Dict, List

TOPICS_DIR = Path("config/topics")
OUTPUT_PATH = Path("config/topics.json")

def parse_markdown_file(md_text: str):
    lines = md_text.splitlines()
    current_year = None
    current_topic = None
    state = None  # "statutory" | "notes" | None
    data = {}
    statutory_acc = []
    notes_acc = []

    def flush_topic():
        nonlocal current_year, current_topic, statutory_acc, notes_acc, data
        if current_year and current_topic:
            topic_obj = {
                "title": current_topic,
                "statutory": statutory_acc[:] if statutory_acc else [],
                "notes": "\n".join(notes_acc).strip() if notes_acc else ""
            }
            data.setdefault(current_year, []).append(topic_obj)
        statutory_acc = []
        notes_acc = []

    for ln in lines:
        ln_strip = ln.strip()
        if ln_strip.startswith("## "):
            flush_topic()
            current_year = ln_strip[3:].strip()
            current_topic = None
            state = None
            statutory_acc = []
            notes_acc = []
            continue
        if ln_strip.startswith("### "):
            flush_topic()
            current_topic = ln_strip[4:].strip()
            state = None
            statutory_acc = []
            notes_acc = []
            continue
        if re.match(r"^\*\*Statutory requirements\*\*", ln_strip, re.IGNORECASE):
            state = "statutory"
            continue
        if re.match(r"^\*\*Notes and guidance", ln_strip, re.IGNORECASE):
            state = "notes"
            continue
        if ln_strip.startswith("- "):
            bullet = ln_strip[2:].strip()
            if state == "statutory":
                statutory_acc.append(bullet)
            else:
                notes_acc.append(bullet)
            continue
        if state == "notes" and ln_strip != "":
            notes_acc.append(ln_strip)
            continue
        if ln_strip.startswith("---"):
            continue

    flush_topic()
    return data

def build_topics_json(topics_dir: Path = TOPICS_DIR, output_path: Path = OUTPUT_PATH):
    combined = {}
    if not topics_dir.exists():
        print(f"No topics directory at {topics_dir}")
        return
    for md in sorted(topics_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        parsed = parse_markdown_file(text)
        for year, topics in parsed.items():
            combined.setdefault(year, [])
            combined[year].extend(topics)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Topics JSON written to {output_path}")

if __name__ == "__main__":
    build_topics_json()
