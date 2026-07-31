# OpenPi / GUI boot — multi-agent + OCR（宿主无关）

**Status:** law for host-agnostic control plane (D5: **no openpi source**).  
**Plan:** `.hermes/plans/2026-07-31_openpi-boot-ma-ocr.md`

## Defaults

| Item | Default |
|------|---------|
| Live MA | ON (`ORPATH_LIVE_SUBAGENT=1`) |
| Control plane | `orpath.bat menu` (not OpenPi panel) |
| OCR | `tools/intake_ocr.py`: ppocr/paddle python → paddle api → **rapidocr** fallback |
| Pi law | `.pi/APPEND_SYSTEM.md` + `.pi/settings.json` |

## Gates

Product gates force `ORPATH_LIVE_SUBAGENT=0`.  
OCR ready claim requires non-placeholder backend on image fixture.

## Operator

```bat
orpath.bat menu
orpath.bat intake --slug x --in fixtures\intake\ocr\scan_sample.png
```
