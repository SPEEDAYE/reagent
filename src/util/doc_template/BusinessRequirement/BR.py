# src/util/doc_template/BusinessRequirement/BR.py — BusinessRequirement marker.
#   Subclass of Document for type-based dispatch; no behavioral changes.
from util.doc_template.chapter import CHAPTER
from util.doc_template.document import Document

class BusinessRequirement(Document):
    def __init__(self, title: str, introduction: str, authors: str):
        super().__init__(title, introduction, authors)

