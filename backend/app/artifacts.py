"""Turn a finished task into downloadable files (zip)."""
import io
import re
import zipfile

from .graph import FINAL_HEADING

EXT = {
    "python": "py", "py": "py", "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
    "tsx": "tsx", "jsx": "jsx", "html": "html", "css": "css", "json": "json", "bash": "sh",
    "sh": "sh", "sql": "sql", "yaml": "yml", "yml": "yml", "java": "java", "go": "go",
    "rust": "rs", "c": "c", "cpp": "cpp", "markdown": "md", "md": "md",
}
FENCE = re.compile(r"```([\w+-]*)[^\n]*\n(.*?)```", re.DOTALL)


def build_files(task) -> dict[str, str]:
    """Latest Developer output -> code files + deliverable.md; always report.md."""
    files: dict[str, str] = {}
    dev = [e for e in task.events if e.agent == "developer"]
    if dev:
        out = dev[-1].output
        # In a debate round the Developer answers the Reviewer first; ship only the final part.
        out = out.split(FINAL_HEADING, 1)[-1].lstrip("\n")
        files["deliverable.md"] = out
        for i, (lang, body) in enumerate(FENCE.findall(out), 1):
            ext = EXT.get(lang.lower(), "txt")
            files[f"code/file_{i}.{ext}"] = body.rstrip() + "\n"
    talk = [e for e in task.events if e.agent in ("developer", "reviewer")]
    if len(talk) > 2:  # more than one Developer/Reviewer exchange
        files["discussion.md"] = "\n\n".join(f"## {i}. {e.name}\n\n{e.output}" for i, e in enumerate(talk, 1)) + "\n"
    files["report.md"] = f"# {task.goal}\n\n{task.final_report}\n"
    return files


def build_zip(task) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in build_files(task).items():
            z.writestr(name, content)
    return buf.getvalue()
