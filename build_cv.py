"""Generate an editable DOCX CV from a reviewed profile."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt

def build(profile_path='cv_profile.json', output_path='resume.docx'):
    p = json.loads(Path(profile_path).read_text(encoding='utf-8'))
    d = Document()
    d.styles['Normal'].font.size = Pt(10)
    d.add_heading(p['name'], 0)
    d.add_paragraph(f"{p['headline']} | {p['location']} | {p['email']}")
    d.add_heading('Professional Summary', 1)
    d.add_paragraph(p['summary'])
    d.add_heading('Technical Skills', 1)
    d.add_paragraph(' • '.join(p['skills']))
    d.add_heading('Professional Experience', 1)
    for e in p['experience']:
        d.add_heading(f"{e['role']} — {e['company']} ({e['dates']})", 2)
        for achievement in e['achievements']:
            d.add_paragraph(achievement, style='List Bullet')
    for heading, key in [('Education', 'education'), ('Certifications', 'certifications')]:
        d.add_heading(heading, 1)
        for item in p.get(key, []):
            d.add_paragraph(item, style='List Bullet')
    d.save(output_path)
    print(f'Created {output_path}; review all placeholders before use.')

if __name__ == '__main__':
    build()
