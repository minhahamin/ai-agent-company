"""Turn a finished task into downloadable files (zip)."""
import io
import re
import zipfile

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
        files["deliverable.md"] = out
        for i, (lang, body) in enumerate(FENCE.findall(out), 1):
            ext = EXT.get(lang.lower(), "txt")
            files[f"code/file_{i}.{ext}"] = body.rstrip() + "\n"
    files["report.md"] = f"# {task.goal}\n\n{task.final_report}\n"
    return files


def build_zip(task) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in build_files(task).items():
            z.writestr(name, content)
    return buf.getvalue()
