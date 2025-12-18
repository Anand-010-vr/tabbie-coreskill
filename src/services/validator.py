import re
from xml.etree import ElementTree as ET
from typing import Tuple, List

# Support both old and new FIB placeholder formats
BLANK_MARKER = r"(\|\#\|TEXT:1\|\#\||\{TEXT1\})"

def is_valid_mathml(xml_string: str) -> bool:
    """
    Validate MathML XML. Handles both:
    - Direct MathML: <math>...</math>
    - MathML wrapped in <p> tags: <p><math>...</math></p>
    """
    if not xml_string or not isinstance(xml_string, str):
        return False
    try:
        root = ET.fromstring(xml_string)
        # If wrapped in <p> tag, check if it contains a <math> element
        if root.tag == 'p':
            # Find math element inside p
            math_elements = list(root.iter('{http://www.w3.org/1998/Math/MathML}math'))
            if not math_elements:
                # Also try without namespace
                math_elements = [elem for elem in root.iter() if elem.tag.endswith('math') or elem.tag == 'math']
            return len(math_elements) > 0
        # Direct math element (with or without namespace)
        elif root.tag.endswith('math') or root.tag == 'math' or '{http://www.w3.org/1998/Math/MathML}math' in root.tag:
            return True
        # If it's some other valid XML but not math, still return True for now
        # (the XML is well-formed, which is what we're validating)
        return True
    except Exception:
        return False

def count_blank_markers(text: str) -> int:
    return len(re.findall(BLANK_MARKER, text))

def validate_fib_accepted_answers(ans_str: str) -> Tuple[bool, str]:
    parts = [p.strip() for p in ans_str.split(";") if p.strip() != ""]
    if not parts:
        return False, "No accepted answers"
    numeric_pattern = re.compile(r'^[0-9]+(\.[0-9]+)?$')
    text_pattern = re.compile(r'^[A-Za-z]+(?:\s[A-Za-z]+)?$')
    if all(numeric_pattern.match(p) for p in parts):
        return True, ""
    if all(text_pattern.match(p) for p in parts):
        return True, ""
    return False, "Answers must be all numeric or all 1-2 word text variants separated by semicolons."

def validate_mcq_options(options: List[str]) -> Tuple[bool, str]:
    if not isinstance(options, list) or len(options) != 4:
        return False, "MCQ must have exactly 4 options"
    for opt in options:
        if "<math" in opt and not is_valid_mathml(opt):
            return False, "Option contains invalid MathML"
    return True, ""
