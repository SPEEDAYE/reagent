# src/util/doc_template/chapter.py — Hierarchical chapter data model.
#
# Outline:
#   paragraph (base)       TITLE, INTRODUCTION, TIMESTAMP, Structure,
#                          SUBCHAPTERS, SECTION, WRITTEN, EXAMPLE
#     ⚠ get_last_content / get_all_content / get_references reference
#     non-existent fields (self.CONTENT / self.REFERENCE) — dead+latent bug.
#   CHAPTER(paragraph)
#     add_subchapter(ch)
#     update_content(content)  append datetime to TIMESTAMP, set Structure
#     get_chapter_structure()  recursive markdown of structure
#     get_all_content(introduction=False, only_show_written=False)
#         markdown render; heading level = len(SECTION.split('.')).
#   print_structure(structure_list)  flatten nested dict list → markdown
from datetime import datetime


class paragraph:
    TITLE : str # title of the chapter
    INTRODUCTION : str # introduction of the chapter
    TIMESTAMP : list
    Structure : list[dict] # 可以和requirements合并
    SUBCHAPTERS: list # list of subchapters
    SECTION: str # section index like 1.1 , 1.2 etc
    WRITTEN: bool # e.g operation system 
    EXAMPLE : bool
    def __init__(self, title: str,  SECTION, INTRODUCTION = ''):
        self.TITLE = title
        self.TIMESTAMP = []
        self.Structure = []
        self.SUBCHAPTERS = []
        self.INTRODUCTION = INTRODUCTION
        self.WRITTEN = False
        self.SECTION = SECTION

class CHAPTER(paragraph):

    def __init__(self, title: str,  SECTION, introduction = ''):
        super().__init__(title, SECTION, introduction)

    def add_subchapter(self, subchapter):
        self.SUBCHAPTERS.append(subchapter)
        
    def update_content(self, content: str):
        self.Structure = content
        self.TIMESTAMP.append(datetime.now())

    def get_last_content(self) -> str:
        if self.CONTENT:
            return self.CONTENT[-1], self.TIMESTAMP[-1]
        return None

    def get_all_content(self) -> list:
        return list(zip(self.CONTENT, self.TIMESTAMP))
    
    def get_subchapters(self) -> list:
        return self.SUBCHAPTERS
    
    def get_references(self) -> list:
        return self.REFERENCE
    
    def get_title(self) -> str:
        return self.TITLE
    
    def get_section(self) -> str:
        return self.SECTION
    
    def get_introduction(self) -> str:
        return self.INTRODUCTION
    
    def get_timestamps(self) -> list:
        return self.TIMESTAMP
    
    def get_chapter_structure(self) -> str:
        result = f"Chapter {self.SECTION} : {self.TITLE}\n"
        result += f"Introduction: {self.INTRODUCTION}\n"
        for subchapter in self.SUBCHAPTERS:
            result += subchapter.get_chapter_structure()
        return result

    def get_all_content(self, introduction = False, only_show_written = False):
        result = ''
        if (not getattr(self, 'WRITTEN', False)) and only_show_written:
            return result
        result += '#' * len(self.SECTION.split('.'))
        result += f" Section {self.SECTION} : {self.TITLE} \n"
        result += f"{print_structure(self.Structure)}\n"
        if introduction:
            result += f"{self.INTRODUCTION}\n"
        for subchapter in self.SUBCHAPTERS:
            result += subchapter.get_all_content(introduction = introduction, only_show_written = only_show_written)
        return result

def print_structure(structure_list:list):
    result = ''
    if structure_list == []:
        return result
    for structure_dict in structure_list:
        for key, value in structure_dict.items():
            if key != 'content':
                result += '\n**' + key + '**:\n'
            if key == 'structure':
                result += print_structure(value)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        result += print_structure([item])
                    else:
                        result += f"- {item}\n"

            elif isinstance(value, dict):
                result += print_structure([value])
            else:
                result += f"{value}\n"
    return result + '\n'
        