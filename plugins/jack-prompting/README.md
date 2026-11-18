# jack-prompting

Install: `/plugin install jack-prompting@jack-cheng-marketplace` · invoke as `/jack-prompting:<skill>`.

Skills that work on the prompt itself, before any code gets written.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`).

- **[iyow](./skills/iyow/SKILL.md)**: "In your own words" — restates what the user's goal is and what problem they are trying to solve, so a misread request is caught before any work begins. Pass the request as the argument: `/jack-prompting:iyow <request>`.
