# Issue: User Notification for Unsupported LLM Parameters (O-series models)

## Problem

When using O-series models (e.g., o4-mini) with the backend, users may encounter errors if they set unsupported parameters such as `top_p` or `temperature` (values other than 1). These errors are currently only visible in backend logs or error messages, and users may not understand why their request failed.

## Solution

### Frontend
- Implement a user notification system that detects when the backend returns an error related to unsupported parameters for O-series models (e.g., litellm.UnsupportedParamsError for `top_p` or `temperature`).
- Display a clear, actionable message to the user, such as:
  > "The selected model (O-series) only supports temperature=1 and does not support top_p. Please adjust your settings."
- Optionally, provide a link to documentation or a help article.

### Documentation
- Update the user documentation to include a section on O-series model limitations:
  - Only `temperature=1` is supported.
  - `top_p` is not supported.
  - Example error messages and how to resolve them.
- Add troubleshooting steps for users encountering these errors.

## Acceptance Criteria
- Users are clearly notified in the frontend UI when they attempt to use unsupported parameters with O-series models.
- Documentation is updated to explain these limitations and provide troubleshooting guidance.

---
*Created on 2025-05-29 by GitHub Copilot*
