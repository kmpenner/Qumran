from lxml import etree
import re

def process_text(text):
    """Convert bracket notation and diacritics to TEI-compliant XML."""
    # Convert fully illegible sections: [ -- ] -> <gap reason="illegible" extent="unknown"/>
    text = re.sub(r'\[\s*--\s*\]', '<gap reason="illegible" extent="unknown"/>', text)

    # Convert partially illegible words: [ -- word] -> <gap reason="illegible" extent="unknown"/> <supplied>word</supplied>
    text = re.sub(r'\[\s*--\s*(.*?)\]', r'<gap reason="illegible" extent="unknown"/> <supplied>\1</supplied>', text)

    # Convert partially illegible words: [word -- ] -> <supplied>word</supplied> <gap reason="illegible" extent="unknown"/>
    text = re.sub(r'\[(.*?)\s*--\s*\]', r'<supplied>\1</supplied> <gap reason="illegible" extent="unknown"/>', text)

    # Convert reconstructed text: [word] -> <supplied>word</supplied>
    text = re.sub(r'\[(.*?)\]', r'<supplied>\1</supplied>', text)

    # Convert probable letters: single or multiple letters with dots above
    text = re.sub(r'((\ẇ)+)', lambda m: f'<unclear cert="high">{m.group(1).replace("̇", "")}</unclear>', text)

    # Convert possible letters: single or multiple letters with circles above
    text = re.sub(r'((\w֯)+)', lambda m: f'<unclear cert="low">{m.group(1).replace("֯", "")}</unclear>', text)

    # Convert unreadable letters: ◌ -> <gap reason="unreadable" extent="unknown"/>
    text = re.sub(r'◌+', '<gap reason="unreadable" extent="unknown"/>', text)

    return text

def add_tei_markup(input_xml):
    """Add TEI XML markup to an input XML document."""
    parser = etree.XMLParser(remove_blank_text=True)

    # Ensure the XML declaration is removed before parsing
    input_xml = re.sub(r"<\?xml.*?\?>", "", input_xml).strip()

    tree = etree.XML(input_xml.encode('utf-8'), parser)

    for s in tree.xpath('//s'):
        if s.text:
            processed_xml = f"<root>{process_text(s.text)}</root>"
            parsed = etree.fromstring(processed_xml)
            s.clear()  # Clear the existing text
            for element in parsed:
                s.append(element)

    output_xml = etree.tostring(tree, encoding='utf-8', pretty_print=True, xml_declaration=True, method="xml").decode('utf-8')
    return output_xml

# Sample input XML
test_xml = """<?xml version='1.0' encoding='utf-8'?>
<text><body><cb n="f1_5" /><lb n="3" /><s>[ -- ]י֯ם צר֯ב֯ ◌[ -- ]</s></body></text>"""

# Process XML with TEI markup
tei_output = add_tei_markup(test_xml)
print(tei_output)
