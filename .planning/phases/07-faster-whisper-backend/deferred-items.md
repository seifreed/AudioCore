# Deferred Items - Plan 07-03

## Pre-existing Test Failure (Out of Scope)

**Issue:** `tests/unit/models/test_segment.py::TestSegmentValidation::test_reject_empty_text` fails

**Root Cause:** Plan 04-03 changed Segment.text to default="" (for VAD-created segments), but Plan 01-03 test expects empty text to raise ValidationError.

**Evidence from STATE.md:**
> **Plan 04-03:** Segment.text defaults to empty string - VAD creates segments before transcription fills text

**Fix Required:** Update test to reflect new model behavior:
```python
def test_accepts_empty_text(self) -> None:
    """Accept empty text for VAD-created segments."""
    segment = Segment(start_time=0.0, end_time=5.0, text="")
    assert segment.text == ""
```

**Scope:** Not related to Faster-Whisper (Plan 07). Fix in Phase 4 cleanup or separate issue.

**Deferred by:** Plan 07-03
