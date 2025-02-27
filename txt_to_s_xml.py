import os
import sys
import xml.etree.ElementTree as ET
import re

def parse_line(line):
    """Parses a line into siglum, column, line number, and content."""
    siglum, rest = line.split(" ", 1)
    column, rest = rest.split(":", 1)
    line_number = rest[:7].strip()
    content = rest[7:].strip()
    return siglum, column, line_number, content

def split_into_sentences(text):
    """Splits text into sentences based on period characters."""
    sentences = re.split(r'(?<!\.)\.(?!\.)', text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]

def create_xml_from_text_file(input_file):
    """Converts a single text file into an XML file with sentences enclosed in <s> elements."""
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found.")
        sys.exit(1)

    output_file = input_file.replace(".txt", ".xml")

    text = ET.Element("text")
    body = ET.SubElement(text, "body")
    current_column = None

    with open(input_file, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            try:
                siglum, column, line_number, content = parse_line(line)
            except ValueError:
                print(f"Skipping invalid line in {input_file}: {line}")
                continue

            if column != current_column:
                ET.SubElement(body, "cb", n=column)
                current_column = column

            lb = ET.SubElement(body, "lb", n=line_number)

            sentences = split_into_sentences(content)
            for sentence in sentences:
                s = ET.SubElement(body, "s")
                s.text = sentence.replace("<", "&lt;").replace(">", "&gt;")

    tree = ET.ElementTree(text)
    with open(output_file, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print(f"Converted {input_file} → {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python txt_to_s_xml.py <input_file>")
        sys.exit(1)

    input_txt_file = sys.argv[1]
    create_xml_from_text_file(input_txt_file)
