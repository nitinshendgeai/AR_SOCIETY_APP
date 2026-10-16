#!/usr/bin/env python3
"""Fail unless a pytest JUnit report shows a real, clean run.

    python scripts/ci/check_test_results.py test-results/backend.xml --min-tests 1000 --max-skipped 5 \\
        --require-package tests.security=50

pytest already exits non-zero when a test fails. This is the second line of defence against a FALSE PASS:
  * the report is missing, empty or unreadable (the run never happened);
  * far fewer tests ran than expected (a directory moved, a path filter, a collection error swallowed);
  * any failure or error is recorded (even if something upstream ignored pytest's exit code);
  * too many tests were skipped (tests quietly turned off);
  * a test package that must stay in the run (for example the security regression tests) has fewer tests than required.
It prints a short summary and, on GitHub Actions, appends it to the job summary page.

Exit code 0 = clean run; 1 = problem (reasons printed).
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET


def summarize(path):
    """(tests, failures, errors, skipped, seconds) summed over every <testsuite> in the report."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise ValueError("no <testsuite> element in the report")
    total = [0, 0, 0, 0, 0.0]
    for s in suites:
        total[0] += int(s.get("tests", 0))
        total[1] += int(s.get("failures", 0))
        total[2] += int(s.get("errors", 0))
        total[3] += int(s.get("skipped", 0))
        total[4] += float(s.get("time", 0))
    return tuple(total)


def count_by_package(path):
    """The dotted classname (e.g. "tests.security.test_x") of every test case in the report."""
    root = ET.parse(path).getroot()
    return [tc.get("classname", "") for tc in root.iter("testcase")]


def check(path, min_tests, max_skipped, required_packages=None):
    """Return (problems, summary_line). `required_packages` maps a dotted prefix (e.g. "tests.security") to the
    minimum number of test cases that must come from it."""
    if not os.path.isfile(path):
        return [f"test report {path} does not exist: the tests did not run"], "no report"
    if os.path.getsize(path) == 0:
        return [f"test report {path} is empty"], "empty report"
    try:
        tests, failures, errors, skipped, seconds = summarize(path)
    except (ET.ParseError, ValueError) as exc:
        return [f"test report {path} is not a valid JUnit file: {exc}"], "unreadable report"
    line = f"{tests} tests, {failures} failed, {errors} errors, {skipped} skipped in {seconds:.0f}s"
    problems = []
    if failures or errors:
        problems.append(f"{failures} failed and {errors} errored tests")
    if tests < min_tests:
        problems.append(f"only {tests} tests ran; at least {min_tests} are expected (is a test directory missing "
                        f"or a collection error being ignored?)")
    if skipped > max_skipped:
        problems.append(f"{skipped} tests were skipped; at most {max_skipped} are allowed")
    for prefix, minimum in (required_packages or {}).items():
        have = sum(1 for c in count_by_package(path) if c == prefix or c.startswith(prefix + "."))
        if have < minimum:
            problems.append(f"only {have} tests came from {prefix}; at least {minimum} must run")
    return problems, line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--min-tests", type=int, default=1,
                    help="fail if fewer tests than this ran (guards against a silently empty run)")
    ap.add_argument("--max-skipped", type=int, default=10**9)
    ap.add_argument("--require-package", action="append", default=[], metavar="PREFIX=N",
                    help="at least N test cases must come from this dotted package, e.g. tests.security=50")
    ap.add_argument("--title", default="Backend tests")
    a = ap.parse_args(argv)

    required = {}
    for item in a.require_package:
        prefix, _, n = item.partition("=")
        if not prefix or not n.isdigit():
            ap.error(f"--require-package expects PREFIX=N, got {item!r}")
        required[prefix] = int(n)
    problems, line = check(a.report, a.min_tests, a.max_skipped, required)
    status = "FAILED" if problems else "passed"
    print(f"{a.title}: {status}: {line}")
    for p in problems:
        print(f"  - {p}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### {a.title}: {'❌ FAILED' if problems else '✅ passed'}\n\n{line}\n\n")
            for p in problems:
                fh.write(f"- {p}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
