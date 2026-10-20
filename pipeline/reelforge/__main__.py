"""ReelForge command line.

  python -m reelforge run INPUT.mp4 -o OUT.mp4 [--project edit.json] [--captions c.json|.srt] [--music m.mp3]
  python -m reelforge analyze INPUT.mp4 -o analysis.json
  python -m reelforge plan analysis.json -o plan.json [--project edit.json]
  python -m reelforge render plan.json -o OUT.mp4
  python -m reelforge verify OUT.mp4 --plan plan.json
"""
import argparse
import json
import os
import sys

from .util import log, require_tools


def _load_project(path):
    if not path:
        return {}
    cfg = json.load(open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(path))

    def fix(p):
        return p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    if cfg.get("captions", {}).get("path"):
        cfg["captions"]["path"] = fix(cfg["captions"]["path"])
    if (cfg.get("music") or {}).get("path"):
        cfg["music"]["path"] = fix(cfg["music"]["path"])
    if cfg.get("source"):
        cfg["source"] = fix(cfg["source"])
    return cfg


def _apply_overrides(cfg, a):
    if getattr(a, "captions", None):
        cfg.setdefault("captions", {})["path"] = os.path.abspath(a.captions)
    if getattr(a, "music", None):
        cfg["music"] = dict(cfg.get("music") or {}, path=os.path.abspath(a.music))
    for k in ("crf", "preset", "codec", "width", "height"):
        v = getattr(a, k, None)
        if v is not None:
            cfg[k] = v
    return cfg


def _analysis_cached(src, workdir, ocr=True):
    from .analyze import analyse
    path = os.path.join(workdir, "analysis.json")
    st = os.stat(src)
    key = [os.path.abspath(src), st.st_size, int(st.st_mtime)]
    if os.path.exists(path):
        a = json.load(open(path))
        if a.get("_key") == key:
            log("Using cached analysis %s" % path)
            return a
    a = analyse(src, with_ocr=ocr)
    a["_key"] = key
    json.dump(a, open(path, "w"), indent=1)
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reelforge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def enc_opts(p):
        p.add_argument("--crf", type=int)
        p.add_argument("--preset")
        p.add_argument("--codec", choices=["h264", "hevc"])
        p.add_argument("--width", type=int)
        p.add_argument("--height", type=int)

    r = sub.add_parser("run", help="analyse + plan + render + verify")
    r.add_argument("input", nargs="?")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--project")
    r.add_argument("--captions")
    r.add_argument("--music")
    r.add_argument("--workdir")
    r.add_argument("--workers", type=int)
    r.add_argument("--preview", type=float, help="render only the first N seconds")
    r.add_argument("--no-ocr", action="store_true")
    enc_opts(r)

    s = sub.add_parser("analyze")
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--no-ocr", action="store_true")

    p = sub.add_parser("plan")
    p.add_argument("analysis")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--project")
    p.add_argument("--captions")
    p.add_argument("--music")
    enc_opts(p)

    d = sub.add_parser("render")
    d.add_argument("plan")
    d.add_argument("-o", "--output", required=True)
    d.add_argument("--workdir")
    d.add_argument("--workers", type=int)
    d.add_argument("--preview", type=float)

    v = sub.add_parser("verify")
    v.add_argument("video")
    v.add_argument("--plan", required=True)
    v.add_argument("--workdir")

    a = ap.parse_args(argv)
    require_tools()

    if a.cmd == "analyze":
        from .analyze import analyse
        json.dump(analyse(a.input, with_ocr=not a.no_ocr), open(a.output, "w"), indent=1)
        return 0

    if a.cmd == "plan":
        from .plan import build_plan
        cfg = _apply_overrides(_load_project(a.project), a)
        plan = build_plan(json.load(open(a.analysis)), cfg)
        json.dump(plan, open(a.output, "w"), indent=1)
        return 0

    if a.cmd in ("render", "run"):
        from .render import render
        from .verify import verify
        out = os.path.abspath(a.output)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        workdir = a.workdir or os.path.splitext(out)[0] + "_work"
        os.makedirs(workdir, exist_ok=True)
        if a.cmd == "run":
            from .plan import build_plan
            cfg = _apply_overrides(_load_project(a.project), a)
            src = a.input or cfg.get("source")
            if not src or not os.path.exists(src):
                sys.exit("Input video not found: %r" % src)
            analysis = _analysis_cached(src, workdir, ocr=not a.no_ocr)
            plan = build_plan(analysis, cfg)
            json.dump(plan, open(os.path.join(workdir, "plan.json"), "w"), indent=1)
        else:
            plan = json.load(open(a.plan))
        limit = int(round(a.preview * plan["fps"])) if a.preview else None
        if limit:
            plan = dict(plan, duration=limit / plan["fps"])
        render(plan, out, workdir, workers=a.workers, limit_frames=limit)
        rep = verify(out, plan, workdir)
        log("Output: %s (%.1f MB) -> %s" % (rep["file"], rep["size_mb"], "ALL CHECKS PASSED" if rep["ok"] else "SOME CHECKS FAILED"))
        return 0 if rep["ok"] else 2

    if a.cmd == "verify":
        from .verify import verify
        plan = json.load(open(a.plan))
        rep = verify(a.video, plan, a.workdir or os.path.splitext(os.path.abspath(a.video))[0] + "_work")
        print(json.dumps(rep, indent=1))
        return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
