import io
import unittest

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.resume import Limits, ResumeError, read_upload, reviewed_text


def pdf_bytes(text=None, *, encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(400, 400)
        if text:
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 16 Tf 20 80 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({
                    NameObject("/F1"): DictionaryObject({
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    })
                })
            })
    if encrypted:
        writer.encrypt("test")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class ResumeTests(unittest.TestCase):
    def test_sources(self):
        self.assertEqual(read_upload("resume.pdf", pdf_bytes("Built a parser")), "Built a parser")
        source = r"\input{file.tex}"
        self.assertEqual(read_upload("resume.tex", source.encode()), source)
        self.assertEqual(reviewed_text("  Built an API  "), "Built an API")

    def test_failures(self):
        for name, data, error in (
            ("resume.pdf", b"%PDF-fake", "unreadable"),
            ("resume.pdf", pdf_bytes(), "scanned"),
            ("resume.pdf", pdf_bytes(encrypted=True), "encrypted"),
            ("resume.tex", b"    ", "empty"),
            ("resume.tex", b"\xff", "UTF-8"),
            ("resume.txt", b"text", "PDF or LaTeX"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ResumeError, error):
                read_upload(name, data)
        with self.assertRaisesRegex(ResumeError, "1-page"):
            read_upload("resume.pdf", pdf_bytes("Text", pages=2), Limits(pages=1))
        with self.assertRaisesRegex(ResumeError, "too large"):
            read_upload("resume.tex", b"test", Limits(file_bytes=3))
        with self.assertRaisesRegex(ResumeError, "characters"):
            reviewed_text("test", Limits(text_chars=3))
