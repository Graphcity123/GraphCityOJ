from __future__ import annotations

import asyncio
import os
import resource
from pathlib import Path

from app.storage import get_languages, get_problem
from app.schemas import EvalStatus


_TOTAL_SCORE = 100


async def run_judge(
    problem_id: str,
    language: str,
    code: str,
    work_dir: Path,
) -> dict:
    """Execute a submission and return structured result."""
    problem = get_problem(problem_id)
    if problem is None:
        return {
            "status": EvalStatus.error.value,
            "score": 0.0,
            "results": [],
            "detail": f"Problem '{problem_id}' not found",
            "counts": 0,
        }

    langs = get_languages()
    lang_info = langs.get(language)
    if lang_info is None:
        return {
            "status": EvalStatus.error.value,
            "score": 0.0,
            "results": [],
            "detail": f"Language '{language}' not supported",
            "counts": 0,
        }

    testcases = problem.get("testcases", [])
    if not testcases:
        return {
            "status": EvalStatus.error.value,
            "score": 0.0,
            "results": [],
            "detail": "No testcases configured",
            "counts": 0,
        }

    time_limit = problem.get("time_limit", lang_info.get("time_limit", 1.0))
    memory_limit = problem.get("memory_limit", lang_info.get("memory_limit", 128))

    compile_cmd = lang_info.get("compile_cmd", "")
    run_cmd = lang_info["run_cmd"]
    extension = lang_info["extension"]

    per_tc_score = _TOTAL_SCORE / len(testcases)

    # Write source file
    work_dir.mkdir(parents=True, exist_ok=True)
    src_path = work_dir / f"src{extension}"
    src_path.write_text(code, encoding="utf-8")

    # Compile if needed
    if compile_cmd:
        compile_full = compile_cmd.format(src=str(src_path), exe=str(work_dir / "program"))
        proc = await asyncio.create_subprocess_shell(
            compile_full,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return {
                "status": EvalStatus.success.value,
                "score": 0.0,
                "results": [{"id": tc_idx + 1, "result": "CE", "time": 0.0, "memory": 0}
                            for tc_idx in range(len(testcases))],
                "detail": stderr.decode("utf-8", errors="replace")[:500],
                "counts": _TOTAL_SCORE,
            }

    # Run each testcase
    results = []
    total_score = 0.0

    for idx, tc in enumerate(testcases):
        tc_result = await _run_testcase(
            run_cmd=run_cmd,
            src_path=str(src_path),
            work_dir=str(work_dir),
            exe_path=str(work_dir / "program") if compile_cmd else "",
            test_input=tc["input"],
            expected_output=tc["output"],
            time_limit=time_limit,
            memory_limit_mb=memory_limit,
            tc_id=idx + 1,
        )
        results.append(tc_result)
        if tc_result["result"] == "AC":
            total_score += per_tc_score

    return {
        "status": EvalStatus.success.value,
        "score": round(total_score, 1),
        "results": results,
        "detail": "",
        "counts": _TOTAL_SCORE,
    }


async def _run_testcase(
    run_cmd: str,
    src_path: str,
    work_dir: str,
    exe_path: str,
    test_input: str,
    expected_output: str,
    time_limit: float,
    memory_limit_mb: int,
    tc_id: int,
) -> dict:
    """Run a single test case."""
    cmd = run_cmd.format(src=src_path, exe=exe_path)

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=test_input.encode()),
                timeout=time_limit,
            )
        except asyncio.TimeoutError:
            try:
                proc.send_signal(signal.SIGKILL)
                await proc.wait()
            except ProcessLookupError:
                pass
            return {"id": tc_id, "result": "TLE", "time": round(time_limit, 2), "memory": 0}

        output = stdout.decode("utf-8", errors="replace").strip()
        expected = expected_output.strip()
        elapsed = time_limit
        mem_used = 0

        if _compare_output(output, expected):
            return {"id": tc_id, "result": "AC", "time": elapsed, "memory": mem_used}
        else:
            return {"id": tc_id, "result": "WA", "time": elapsed, "memory": mem_used}

    except asyncio.TimeoutError:
        return {"id": tc_id, "result": "TLE", "time": round(time_limit, 2), "memory": 0}
    except Exception:
        return {"id": tc_id, "result": "RE", "time": 0.0, "memory": 0}


def _compare_output(got: str, expected: str) -> bool:
    got_lines = [line.rstrip() for line in got.splitlines()]
    exp_lines = [line.rstrip() for line in expected.splitlines()]
    # Remove trailing empty lines
    while got_lines and got_lines[-1] == "":
        got_lines.pop()
    while exp_lines and exp_lines[-1] == "":
        exp_lines.pop()
    return got_lines == exp_lines


def _set_limits(memory_mb: int):
    """Return a preexec_fn that sets resource limits."""
    def _fn():
        mem_bytes = memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        except Exception:
            pass
    return _fn
