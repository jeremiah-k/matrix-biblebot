# Direct-Only Trigger Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the direct-only trigger model by removing all remaining stale references to the multi-mode trigger system that never shipped.

**Architecture:** The codebase is already direct-only. This plan removes stale documentation, fixes misleading test names/docstrings, and adds one missing test case.

**Tech Stack:** Python 3.10+, pytest

---

## File Structure

| Action | File                                                  | Responsibility                          |
| ------ | ----------------------------------------------------- | --------------------------------------- |
| Delete | `docs/superpowers/plans/2026-04-17-trigger-policy.md` | Old multi-mode plan, entirely stale     |
| Modify | `tests/test_edge_cases.py`                            | Fix misleading docstring                |
| Modify | `tests/test_integration_patterns.py`                  | Rename test, fix misleading name        |
| Modify | `tests/test_trigger_policy.py`                        | Add missing "Romans 8:28 ESV" test case |

---

### Task 1: Delete stale multi-mode plan

**Files:**

- Delete: `docs/superpowers/plans/2026-04-17-trigger-policy.md`

This document describes `TriggerMode.SMART`, `TriggerMode.ANYWHERE`, `detect_references_anywhere` migration, `command_prefix`, `EMBEDDED_REFERENCE_PATTERNS`, and other features that were never implemented on main. It is entirely misleading and should be deleted.

- [ ] **Step 1:** Delete `docs/superpowers/plans/2026-04-17-trigger-policy.md`
- [ ] **Step 2:** Verify `docs/superpowers/plans/` only contains the new plan file

```bash
rm docs/superpowers/plans/2026-04-17-trigger-policy.md
ls docs/superpowers/plans/
```

Expected: Only `2026-04-17-direct-only-trigger-cleanup.md` remains.

---

### Task 2: Fix misleading test docstring in test_edge_cases.py

**Files:**

- Modify: `tests/test_edge_cases.py:94-98`

The `test_extremely_long_messages` method has a docstring that mentions "detects embedded scripture references" and "enables partial-reference detection" but the test body sends `"John 3:16"` as a direct reference. The docstring is stale from before the direct-only refactor.

- [ ] **Step 1:** Update the docstring to accurately describe the test

Old docstring (lines 94-98):

```python
    async def test_extremely_long_messages(self, mock_config, mock_client):
        """
        Verify on_room_message handles extremely long messages and detects embedded scripture references.

        Sets up a BibleBot with mocked config/client, enables partial-reference detection, and patches get_bible_text to return a valid verse. Sends an ~10k-character message that contains an embedded reference ("John 3:16") and asserts the bot processes it without crashing and attempts to send a reply (client.room_send is called).
        """
```

New docstring:

```python
    async def test_extremely_long_messages(self, mock_config, mock_client):
        """
        Verify on_room_message handles a direct scripture reference correctly.

        Sets up a BibleBot with mocked config/client, patches get_bible_text to return a valid verse, and sends "John 3:16" as a direct reference. Asserts the bot processes it without crashing and attempts to send a reply (client.room_send is called).
        """
```

Also update the inline comment at line 114-115:

Old:

```python
            # Test with extremely long message containing embedded scripture reference
            # This tests both long message handling and partial reference detection
```

New:

```python
            # Test with a direct scripture reference
```

- [ ] **Step 2:** Run `python -m pytest tests/test_edge_cases.py::TestEdgeCases::test_extremely_long_messages -v`

Expected: PASS

---

### Task 3: Rename misleading test in test_integration_patterns.py

**Files:**

- Modify: `tests/test_integration_patterns.py:457`

The test `test_api_integration_chain_partial_mode_disabled` references "partial mode" which never existed as a concept. Rename to `test_api_integration_chain_embedded_reference_ignored`.

- [ ] **Step 1:** Rename the test method

Old:

```python
    async def test_api_integration_chain_partial_mode_disabled(
```

New:

```python
    async def test_api_integration_chain_embedded_reference_ignored(
```

- [ ] **Step 2:** Run `python -m pytest tests/test_integration_patterns.py::TestAPIIntegration::test_api_integration_chain_embedded_reference_ignored -v`

Expected: PASS

---

### Task 4: Add missing test case for "Romans 8:28 ESV"

**Files:**

- Modify: `tests/test_trigger_policy.py`

The user specified that "Romans 8:28 ESV" should trigger. Add a test for this specific case to `TestDirectOnlyMode`.

- [ ] **Step 1:** Add test after `test_translation_suffix` in `TestDirectOnlyMode`

```python
    def test_translation_uppercase_with_chapter_verse(self):
        result = detect_trigger("Romans 8:28 ESV", "kjv")
        assert result is not None
        assert result.passage == "Romans 8:28"
        assert result.translation == "esv"
        assert result.source == TriggerSource.DIRECT
```

- [ ] **Step 2:** Run `python -m pytest tests/test_trigger_policy.py::TestDirectOnlyMode -v`

Expected: All tests PASS including new test.

---

### Task 5: Run full test suite

- [ ] **Step 1:** Run `python -m pytest tests/ -q --tb=short`

Expected: 534+ passed (533 existing + new test), 0 failed.

- [ ] **Step 2:** Commit all changes

```bash
git add docs/superpowers/plans/ tests/
git commit -m "chore: clean up stale multi-mode trigger references and add test coverage"
```
