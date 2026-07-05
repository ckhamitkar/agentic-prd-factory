# Product Context

This file defines the product context / business model the factory scores opportunities against. Every agent reads it and evaluates ideas, features, and recommendations against it. **Replace it with your own** to point the factory at whatever product or business you are building.

Below is a generic, illustrative example. It is not a real product - it exists only to show the shape of a useful product context.

---

## Example: Plain-Language Medication Information Assistant

### What it is
An **educational** tool that helps people understand the labels and instructions that come with their medications - explaining terms, dosing instructions, and warnings in plain language.

### What it is NOT
This is educational information only. It does **not** diagnose, screen for, assess, or treat any condition, and it does not give medical advice. It always directs the user to a licensed pharmacist, doctor, or other qualified professional for actual decisions about their health or medications.

### Principles
- **Clarity** - explain things in plain, everyday language; assume no medical training.
- **Accessibility** - work for people with a wide range of literacy, languages, and devices.
- **Privacy** - collect as little personal information as possible; never sell or expose user data.
- **Sustainability** - the product must be affordable to run and viable for the organization building it.

### Boundaries the agents must respect
- Never use regulated verbs (diagnose, screen, assess, treat, prescribe).
- Always recommend consulting a qualified professional for any real decision.
- Prefer solutions that keep sensitive user data minimal and well-protected.
