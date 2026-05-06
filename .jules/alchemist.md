## 2024-05-24 - E2E Test Limitations in Sandbox
**Transformation:** Attempted to refactor environment sterilization and path resolution in `wrapper.py`.
**Result:** E2E tests (`test_e2e.py`) consistently failed with "FATAL ERROR: Bundled compiler binary 'ghc' could not be located" even on a clean checkout.
**Lesson:** The `ghc-bindist` directory containing the native binaries is not present in the testing sandbox environment. Consequently, E2E tests cannot be used to reliably verify refactorings here. Verification must rely on the mocked unit tests (`test_wrapper.py`) and static analysis.
