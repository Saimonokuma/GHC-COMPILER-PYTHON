## 2024-05-06 - Eager Evaluation Trap
**Transformation:** Replaced `if/elif` chain with dictionary-based platform mappings.
**Result:** Code became eager, trying to run platform-specific paths on all platforms before mapping. Code review raised safety concerns.
**Lesson:** Python mappings for complex code paths require lazy evaluation (`lambda`) to match `if/elif` logic closely, especially when functions have side effects or paths only exist conditionally based on the platform.
