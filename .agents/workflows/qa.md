---
description: Manual Verification Matrix - Every completed implementation MUST include a **Manual Verification Matrix**.
---

The matrix should provide the developer with a concise checklist to manually verify the implementation.

For each significant feature, include:

| Scenario | Test Action / Trigger | Expected Behavior |
|----------|-----------------------|-------------------|

Guidelines:

- Focus on the functionality introduced by the implementation.
- Include both normal user flows and important edge cases.
- Describe exactly what the developer should do.
- Describe exactly what should happen.
- Include regression checks where applicable.
- Do not include implementation details or internal code execution unless they help explain the expected behavior.
- Keep the matrix concise (typically 5–10 scenarios).

Common scenarios to consider:

- Primary feature flow
- Invalid user input
- Duplicate/repeated actions
- Page refresh
- Navigation between pages/views
- Browser back/forward
- Multiple tabs/windows
- Slow or failed network requests
- Persistence after reload
- Regression of related features

The goal is to give the developer a quick manual QA checklist before considering the implementation complete.