#!/usr/bin/env python
# src/reagent/main.py — CLI entry + stage-6 SRS generator.
#
# Outline:
#   RequirementSpecificationrun(document_template, document_skeleton,
#                               doc_content, chapter_dependence,
#                               SRS_Reference, srs_example_path)
#     Iterates chapter_sequence = topological_sort(chapter_dependence).
#     For each chapter:
#       - SRSplaningCrew produces a writing plan (srs_planning.md)
#       - SRSev writes the chapter (software_requirements_specification_chapter.md)
#       - post_process() assembles into in-memory SRS document + pickles +
#         rewrites SRS.md (with get_dependence_appendix).
#
#   main()  CLI entry. Arguments:
#           --project_name, --description_file, --data_path,
#           --srs_example_path, --srs_template
#     Loads description → optional RequirementsExtractionRun (if --data_path)
#                      → StandardProcessrun  ← ⚠ skips BRDevrun internally
#                      → NonStandardProcessrun
#                      → RequirementSpecificationrun
#
# NOTE: The API path (backend/services/execution.py) does NOT call
# StandardProcessrun; it invokes each stage directly, including BRDevrun.
import sys
import warnings
from datetime import datetime
import os
from pathlib import Path
import hashlib
import json
import pickle
import time
CURRENT = Path(__file__).resolve()
ROOT = CURRENT.parents[2]  # 根据你的层级调整
SRC_ROOT = ROOT / "src"
for _path in (SRC_ROOT, CURRENT.parent):
    _value = str(_path)
    if _value not in sys.path:
        sys.path.insert(0, _value)
from dotenv import load_dotenv
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
_project_root = str(Path(__file__).resolve().parents[2])
os.chdir(_project_root)
load_dotenv(os.path.join(_project_root, ".env"))
from util import *
from StandardProcess import StandardProcessrun
from NonStandardProcess import NonStandardProcessrun
import argparse
from reagent.logger import log_event
from reagent.progress import TerminalProgress


def _write_srs_completion_marker(chapter_count: int) -> None:
    """Commit proof that every SRS chapter and final files reached disk."""
    store_path = Path(get_store_path())
    srs_path = store_path / "SRS.md"
    pickle_path = store_path / "SRS.pkl"
    marker_dir = store_path / ".pipeline"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "srs_complete.json"
    marker_temp = marker_dir / "srs_complete.json.tmp"
    payload = {
        "completed": True,
        "chapter_count": chapter_count,
        "completed_at": datetime.now().astimezone().isoformat(),
        "files": {
            "SRS.md": hashlib.sha256(srs_path.read_bytes()).hexdigest(),
            "SRS.pkl": hashlib.sha256(pickle_path.read_bytes()).hexdigest(),
        },
    }
    marker_temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    marker_temp.replace(marker_path)


def RequirementSpecificationrun(document_template, document_skeleton, doc_content, chapter_dependence, SRS_Reference, srs_example_path):
    from RequirementSpecification import SRSev, SRSplaningCrew
    chapter_sequence = topological_sort(chapter_dependence)
    SRS_initial_template = document_template
    SRS = parse_skeleton_to_document_template(
        skeleton_json=document_skeleton,
        authors='csl-gpt4.1'
    )
    
    # ========== 逐章生成 SRS ==========
    def post_process():
        chapter = get_SRS_chapter()
        chapter = json.loads(chapter)
        SRS.write_file(chapter) 
        with open(f"{get_store_path()}/SRS.pkl", "wb") as f:
            pickle.dump(SRS, f)
        with open(f"{get_store_path()}/SRS.md", "w", encoding="utf-8") as f:
            f.write(f"{SRS.get_whole_document(only_show_written = True)}{get_dependence_appendix(SRS_Reference)}")
        # Commit completion before CrewAI disposes the final chapter's browser
        # resources. A native Chromium crash during cleanup must not erase the
        # fact that every chapter and both final artifacts already reached disk.
        if i == len(chapter_sequence) - 1:
            _write_srs_completion_marker(len(chapter_sequence))
    SRS_chapter_dict = {}
    SRS_example = split_markdown_by_h2(read_markdown(srs_example_path))
    for i, chapter in enumerate(chapter_sequence):
        dependency_chapter_list = [index for index in chapter_dependence[chapter]]
        SRS_exmaple_inputs = {
            'SRS_example': SRS_example[i + 1], # 忽略第一个
            'SRS_reference':get_reference(SRS_Reference[i],artifact = False),
            'dependence_chapter_content' : ''.join([print_doc_content(doc_content[i]) for i in range(len(doc_content)) if doc_content[i]['chapter_index'] in dependency_chapter_list ])
        }
        run_with_retry(
            SRSplaningCrew,
            inputs=SRS_exmaple_inputs,
            name=f"SRS Chapter planning {i}",
        )
        prompt = get_SRS_planning()
        SRS_inputs = {
            'SRS_chapter_structure': SRS_initial_template.SUBCHAPTERS[i].get_all_content(introduction = True),
            'reference': get_reference(SRS_Reference[i]),
            'chapter_reference' : ''.join([SRS_chapter_dict[i] for i in dependency_chapter_list]),
            'prompt' : prompt,
            'chapter_index' : i
        }
        run_with_retry(
            SRSev,
            inputs=SRS_inputs,
            name=f"SRS Chapter {i+1}",
            post_process_callable=post_process,
        )
        SRS_chapter_dict[chapter] = get_SRS_chapter()
    with open(f"{get_store_path()}/SRS.md", "w", encoding="utf-8") as f:
        f.write(f"{SRS.get_whole_document(only_show_written = True)}{get_dependence_appendix(SRS_Reference)}")
    _write_srs_completion_marker(len(chapter_sequence))


# 示例1： 课程安排系统
# project_name = '课程安排系统'
# Description = "我们学校课程表经常混乱，所以我想开发一个课程安排系统，老师能查课程，学生能看自己的课表。"
# 我们希望开发一个科研人员管理平台，其中每个人可以注册，加入小组，每个人可以写工作报告；系统可以对报告进行数据分析、可视化报告，总结报告，分析、可视化报告变化
# project_name = '自动化软件源代码审查平台'

def _slug(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value)
    return "-".join(part for part in safe.split("-") if part)[:64] or "run"


def _default_model_id() -> str:
    for key in ("REAGENT_MODEL_ID", "LLM_MODEL", "OPENAI_MODEL", "DEEPSEEK_MODEL", "QWEN_MODEL"):
        value = os.getenv(key)
        if value:
            return _slug(value)
    return "model"


def _init_experiment_run(args) -> tuple[str, str, str]:
    model_id = _slug(args.model_id or _default_model_id())
    script_id = _slug(args.script_id)
    run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{script_id}-{model_id}"
    store_path = args.store_path or os.path.join(args.experiment_root, run_id)

    set_store_path(store_path)
    os.environ["REAGENT_RUN_ID"] = run_id
    os.environ["REAGENT_MODEL_ID"] = model_id
    os.environ["REAGENT_OUTPUT_PATH"] = store_path

    command = "python main.py " + " ".join(sys.argv[1:])
    Path(store_path).mkdir(parents=True, exist_ok=True)
    Path(store_path, "command.txt").write_text(command + "\n", encoding="utf-8")
    Path(store_path, "README.md").write_text(
        "\n".join([
            f"# {run_id}",
            "",
            f"- Project: {args.project_name}",
            f"- Script id: {script_id}",
            f"- Model id: {model_id}",
            f"- Output path: `{store_path}`",
            "",
            "## Command",
            "",
            "```bash",
            command,
            "```",
            "",
        ]),
        encoding="utf-8",
    )
    return run_id, model_id, store_path


def main():
    parser = argparse.ArgumentParser(
        description="Run automated requirement engineering pipeline"
    )

    parser.add_argument(
        "--project_name",
        type=str,
        default="自动化软件源代码审查平台",
        help="项目名称"
    )

    parser.add_argument(
        "--description_file",
        type=str,
        required=True,
        help="项目描述文本文件路径"
    )
    parser.add_argument(
        "--data_path",
        type=str,
        default=None,
        help="项目数据路径"
    )

    parser.add_argument(
        "--srs_example_path",
        type=str,
        default="src/util/doc_template/document_example.md",
        help="SRS 示例模板路径"
    )

    parser.add_argument(
        "--srs_template",
        type=str,
        default=None,
        help="SRS 模板（可选）"
    )
    parser.add_argument(
        "--script_id",
        type=str,
        default="cli",
        help="用于 experiment run 命名的脚本标识"
    )
    parser.add_argument(
        "--model_id",
        type=str,
        default=None,
        help="用于 experiment run 命名的模型标识"
    )
    parser.add_argument(
        "--run_id",
        type=str,
        default=None,
        help="显式指定 experiment run id"
    )
    parser.add_argument(
        "--experiment_root",
        type=str,
        default="experiment",
        help="实验 run 根目录"
    )
    parser.add_argument(
        "--store_path",
        type=str,
        default=None,
        help="显式指定本次输出目录；默认由 experiment_root/run_id 生成"
    )

    args = parser.parse_args()
    run_id, model_id, store_path = _init_experiment_run(args)
    progress = TerminalProgress(run_id=run_id, model=model_id, output_path=store_path)
    progress.update("setup", "experiment run initialized")
    log_event("info", "experiment run initialized", run_id=run_id, model_id=model_id, output_path=store_path)

    # 读取描述
    with open(args.description_file, "r", encoding="utf-8") as f:
        Description = f.read()
        

    if args.data_path:
        from RequirementExtraction import RequirementsExtractionRun
        if not os.path.exists(args.data_path):
            raise FileNotFoundError("数据文件未找到")
        RequirementsExtractionRun(
            args.project_name,
            Description,
            args.data_path
            ).run()
    
    # === Step 1: 标准流程 ===
    (
        document_template,
        document_skeleton,
        doc_planning,
        chapter_dependence,
        artifact_planing,
    ) = StandardProcessrun(
        project_name=args.project_name,
        Description=Description,
        srs_example_path=args.srs_example_path,
        SRS_template=args.srs_template,
    )
    progress.update("standard_process", "standard requirement pipeline completed")

    # === Step 2: 非标准流程 ===
    NonStandardProcessrun(
        project_name=args.project_name,
        Description=Description,
        artifact_planing=artifact_planing,
    )
    progress.update("non_standard", "non-standard artifacts completed")

    # === Step 3: 需求规格说明生成 ===
    RequirementSpecificationrun(
        document_template,
        document_skeleton,
        doc_planning,
        chapter_dependence,
        SRS_Reference=artifact_planing,
        srs_example_path=args.srs_example_path,
    )
    progress.update("srs_generation", "SRS generation completed")
    log_event("info", "experiment run finished", run_id=run_id, output_path=store_path)


if __name__ == "__main__":
    main()
        
    
