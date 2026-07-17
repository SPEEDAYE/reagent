# src/util/doc_template/document.py — Document root container + skeleton parser.
#
# Outline:
#   Document:
#     TITLE, INTRODUCTION, AUTHOR, SUBCHAPTERS
#     add_subchapter(ch)          appends and sets SECTION
#                                 (⚠ off-by-one: uses len+1 after append)
#     get_structure()             titles+sections summary
#     get_overall_structure(ch=-1) recursive structure (-1 = whole doc)
#     get_document_structure()    title + authors + flat subchapter list
#     get_whole_document(introduction=False, only_show_written=False)
#                                 concatenate CHAPTER.get_all_content() outputs
#     get_last_modfication_time() recursive max of timestamps
#     write_file(chapter_dict)    navigate by chapter_index and write chapter
#     write_chapter(doc_chapter, chapter)  recursively update structure
#
#   parse_skeleton_to_document_template(skeleton_json, authors)
#     JSON → SoftwareRequirementSpecification with ≤4 nested CHAPTER levels.
#     ⚠ Depth is hardcoded; deeper JSON silently truncates.
from datetime import datetime
from util.doc_template.chapter import CHAPTER

class Document:
    TITLE : str
    INTRODUCTION : str
    Author: str

    def __init__(self, title: str, introduction: str, authors: str):
        self.TITLE = title
        self.INTRODUCTION = introduction
        self.AUTHOR = authors
        self.SUBCHAPTERS = []

    def get_structure(self) -> str:
        result = ''
        result += "Document Structure:\n"
        result += f"Title: {self.TITLE}\n"
        result += f"Introduction: {self.INTRODUCTION}\n"
        for subchapter in self.SUBCHAPTERS:
            result += f"- {subchapter.SECTION} {subchapter.TITLE}\n"
            result += f"{subchapter.INTRODUCTION}\n"
        return result

    def get_overall_structure(self, chapter = -1) -> str:
        result = ''
        if chapter < 0 :
            result += "Document Structure:\n"
            result += f"Title: {self.TITLE}\n"
            result += f"Introduction: {self.INTRODUCTION}\n"
            for subchapter in self.SUBCHAPTERS:
                result += subchapter.get_chapter_structure()
        elif chapter >= 0:
            result += self.SUBCHAPTERS[chapter].get_chapter_structure()
        else:
            raise("wrong chapter number !")
        return result

    def add_subchapter(self, subchapter: CHAPTER):
        subchapter.SECTION = f"{len(self.SUBCHAPTERS) + 1}"
        self.SUBCHAPTERS.append(subchapter)

    def get_authors(self) -> str:
        return self.AUTHOR
    
    def get_title(self) -> str:
        return self.TITLE
    
    def get_introduction(self) -> str:
        return self.INTRODUCTION

    def get_last_modfication_time(self) -> datetime:
        latest_time = None
        for subchapter in self.SUBCHAPTERS:
            timestamps = subchapter.get_timestamps()
            if timestamps:
                subchapter_latest = max(timestamps)
                if latest_time is None or subchapter_latest > latest_time:
                    latest_time = subchapter_latest
        return latest_time
    
    def get_whole_document(self, introduction = False, only_show_written = False):
        result = ''
        # result += f"Document Title: {self.TITLE}"
        # result += f"Introduction: {self.INTRODUCTION}"
        # result += f"Author(s): {self.AUTHOR}\n"
        # pdb.set_trace()
        for subchapter in self.SUBCHAPTERS:
            result += subchapter.get_all_content( introduction = introduction, only_show_written = only_show_written)
        return result
    
    def get_document_structure(self):
        result = ''
        result += f"Document Title: {self.TITLE}"
        result += f"Introduction: {self.INTRODUCTION}"
        result += f"Author(s): {self.AUTHOR}\n"
        # pdb.set_trace()
        for subchapter in self.SUBCHAPTERS:
            result += subchapter.get_chapter_structure()
        return result

    def write_file(self, chapter: dict):
        write_chapter = self
        idx = int(chapter['chapter_index'])
        if idx < len(write_chapter.SUBCHAPTERS):
            write_chapter = write_chapter.SUBCHAPTERS[idx]
            write_chapter.TITLE = chapter['title']
            write_chapter.SECTION = chapter['chapter_index']
        else:
            write_chapter.SUBCHAPTERS.append(CHAPTER(title=chapter['title'], SECTION=chapter['chapter_index'],))
            write_chapter = write_chapter.SUBCHAPTERS[-1]
        self.write_chapter(write_chapter, chapter)

    def write_chapter(self,document_chapter, chapter):
        document_chapter.WRITTEN = True
        document_chapter.Structure = chapter['structure']
        for index, subchapter in enumerate(chapter.get('subchapter', [])):
            if len(document_chapter.SUBCHAPTERS) > index: 
                document_chapter.SUBCHAPTERS[index].TITLE = subchapter['title']
                document_chapter.SUBCHAPTERS[index].SECTION = subchapter['chapter_index']
                document_chapter.SUBCHAPTERS[index].Structure = subchapter['structure']
                self.write_chapter(document_chapter=document_chapter.SUBCHAPTERS[index], chapter=subchapter)
            else:
                new_chapter = CHAPTER(title=subchapter['title'], SECTION=subchapter['chapter_index'],)
                new_chapter.Structure = subchapter['structure']
                document_chapter.add_subchapter(new_chapter)
                self.write_chapter(document_chapter=new_chapter, chapter=subchapter)
 

def parse_skeleton_to_document_template(skeleton_json: str, authors: str):
    """
    将 Agent 输出的文档骨架（JSON 字符串）解析为 SoftwareRequirementSpecification 模板结构，
    支持最多四级标题（1 / 1.1 / 1.1.1 / 1.1.1.1）。

    skeleton_json: 来自 Agent 的 JSON 输出（str）
    authors: 文档作者，用于初始化 SRS

    返回:
        SoftwareRequirementSpecification 对象（带完整章节结构）
    """
    import json
    from util.doc_template.SoftwareRequirementSpecification.SRS import SoftwareRequirementSpecification
    from util.doc_template.chapter import CHAPTER

    # 解析 JSON
    skeleton = json.loads(skeleton_json)

    # 初始化 SRS 根文档
    SRS = SoftwareRequirementSpecification(
        title="Software Requirement Specification",
        introduction="This document outlines the software requirements for the project.",
        authors=authors
    )

    # ---------- 一级标题 ----------
    for chapter_obj in skeleton:
        level1_chapter = CHAPTER(
            title=chapter_obj.get("title", "Untitled Section"),
            SECTION=chapter_obj.get("chapter_index", "")
        )
        level1_chapter.update_content(chapter_obj.get("structure", []))
        SRS.add_subchapter(level1_chapter)

        # ---------- 二级标题 ----------
        for sub2 in chapter_obj.get("subchapter", []):
            level2_chapter = CHAPTER(
                title=sub2.get("title", "Untitled Section"),
                SECTION=sub2.get("chapter_index", "")
            )
            level2_chapter.update_content(sub2.get("structure", []))
            level1_chapter.add_subchapter(level2_chapter)

            # ---------- 三级标题 ----------
            for sub3 in sub2.get("subchapter", []):
                level3_chapter = CHAPTER(
                    title=sub3.get("title", "Untitled Section"),
                    SECTION=sub3.get("chapter_index", "")
                )
                level3_chapter.update_content(sub3.get("structure", []))
                level2_chapter.add_subchapter(level3_chapter)

                # ---------- 四级标题 ----------
                for sub4 in sub3.get("subchapter", []):
                    level4_chapter = CHAPTER(
                        title=sub4.get("title", "Untitled Section"),
                        SECTION=sub4.get("chapter_index", "")
                    )
                    level4_chapter.update_content(sub4.get("structure", []))
                    level3_chapter.add_subchapter(level4_chapter)

    return SRS
