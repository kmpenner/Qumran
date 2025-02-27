import os
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

def create_xml_from_text_file(input_file, output_file):
    """Converts a text file into an XML file with sentences enclosed in <s> elements."""
    # Create the root elements
    text = ET.Element("text")
    body = ET.SubElement(text, "body")

    current_column = None

    with open(input_file, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            # Parse the line
            siglum, column, line_number, content = parse_line(line)

            # Add a new column break if column changes
            if column != current_column:
                ET.SubElement(body, "cb", n=column)
                current_column = column

            # Add a line break
            lb = ET.SubElement(body, "lb", n=line_number)

            # Split content into sentences and add <s> elements
            sentences = split_into_sentences(content)
            for sentence in sentences:
                s = ET.SubElement(body, "s")
                s.text = sentence.replace("<", "&lt;").replace(">", "&gt;")

    # Write the XML to the output file
    tree = ET.ElementTree(text)
    with open(output_file, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

def convert_folder_to_xml(input_folder, output_folder):
    """Converts all text files in a folder to XML files."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.endswith(".txt"):
            input_file = os.path.join(input_folder, filename)
            output_file = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.xml")
            create_xml_from_text_file(input_file, output_file)

# Example usage
input_folder = "C:\\Users\\kmpen\\OneDrive\\Research\\Logos\\DSS\\output_files"  # Replace with the path to your folder with text files
output_folder = input_folder  # Replace with the path to your desired output folder
convert_folder_to_xml(input_folder, output_folder)
