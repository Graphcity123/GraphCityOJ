from __future__ import annotations

import asyncio
import os
import resource
import signal
import time
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
    problem = await get_problem(problem_id)
    if problem is None:
        return {
            "status": EvalStatus.error.value,
            "score": 0,
            "results": [],
            "detail": f"Problem '{problem_id}' not found",
            "counts": 0,
        }

    langs = await get_languages()
    lang_info = langs.get(language)
    if lang_info is None:
        return {
            "status": EvalStatus.error.value,
            "score": 0,
            "results": [],
            "detail": f"Language '{language}' not supported",
            "counts": 0,
        }

    testcases = problem.get("testcases", [])
    if not testcases:
        return {
            "status": EvalStatus.error.value,
            "score": 0,
            "results": [],
            "detail": "No testcases configured",
            "counts": 0,
        }

    time_limit = problem.get("time_limit", lang_info.get("time_limit", 1.0))
    memory_limit = problem.get("memory_limit", lang_info.get("memory_limit", 128))

    compile_cmd = lang_info.get("compile_cmd", "")
    run_cmd = lang_info["run_cmd"]
    extension = lang_info.get("file_ext", ".py")

    per_tc_score = _TOTAL_SCORE / len(testcases) if testcases else 0
    total_counts = _TOTAL_SCORE

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
                "score": 0,
                "results": [{"id": tc_idx + 1, "result": "CE", "time": 0.0, "memory": 0}
                            for tc_idx in range(len(testcases))],
                "detail": stderr.decode("utf-8", errors="replace")[:500],
                "counts": _TOTAL_SCORE,
            }

    # Run testcases concurrently (max 4 at a time)
    sem = asyncio.Semaphore(4)

    async def _run_one(idx: int, tc: dict) -> dict:
        async with sem:
            return await _run_testcase(
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

    tasks = [_run_one(i, tc) for i, tc in enumerate(testcases)]
    results = await asyncio.gather(*tasks)

    total_score = sum(
        per_tc_score for r in results if r["result"] == "AC"
    )

    return {
        "status": EvalStatus.success.value,
        "score": total_score,
        "results": results,
        "detail": "",
        "counts": total_counts,
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
    """Run a single test case inside firejail sandbox."""
    cmd = run_cmd.format(src=src_path, exe=exe_path)
    mem_bytes = memory_limit_mb * 1024 * 1024
    timeout_sec = int(time_limit) + 2  # small cushion

    # Wrap in firejail for cgroup-based memory isolation
    hh = timeout_sec // 3600
    mm = (timeout_sec % 3600) // 60
    ss = timeout_sec % 60
    jail_cmd = (
        f"firejail --quiet --noprofile "
        f"--rlimit-as={mem_bytes} "
        f"--timeout={hh:02d}:{mm:02d}:{ss:02d} "
        f"-- {cmd}"
    )

    try:
        proc = await asyncio.create_subprocess_shell(
            jail_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )

        start_time = time.perf_counter()

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=test_input.encode()),
                timeout=time_limit,
            )
        except asyncio.TimeoutError:
            elapsed = round(time.perf_counter() - start_time, 2)
            try:
                os.kill(proc.pid, signal.SIGKILL)
                await proc.wait()
            except ProcessLookupError:
                pass
            return {"id": tc_id, "result": "TLE",
                    "time": elapsed, "memory": 0}

        elapsed = round(time.perf_counter() - start_time, 2)

        # Memory from OS: max RSS of child processes (KB on Linux)
        try:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            mem_mb = usage.ru_maxrss // 1024
        except Exception:
            mem_mb = 0

        # MLE check against OS-reported max
        if mem_mb > memory_limit_mb:
            return {"id": tc_id, "result": "MLE",
                    "time": elapsed, "memory": int(mem_mb)}

        output = stdout.decode("utf-8", errors="replace").strip()
        expected = expected_output.strip()

        if _compare_output(output, expected):
            return {"id": tc_id, "result": "AC",
                    "time": elapsed, "memory": int(mem_mb)}
        else:
            return {"id": tc_id, "result": "WA",
                    "time": elapsed, "memory": int(mem_mb)}

    except asyncio.TimeoutError:
        return {"id": tc_id, "result": "TLE",
                "time": round(time_limit, 2), "memory": 0}
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


