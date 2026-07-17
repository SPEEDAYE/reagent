# src/util/doc_template/SoftwareRequirementSpecification/SRS.py — SRS marker.
#   Subclass of Document for type-based dispatch; no behavioral changes.
from util.doc_template.chapter import CHAPTER
from util.doc_template.document import Document

class SoftwareRequirementSpecification(Document):
    def __init__(self, title: str, introduction: str, authors: str):
        super().__init__(title, introduction, authors)

